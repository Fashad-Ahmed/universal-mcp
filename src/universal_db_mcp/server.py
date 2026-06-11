"""Main FastMCP server for Universal Database MCP."""

import sys
import json
import asyncio
import argparse
import collections
import sqlparse
from sqlparse.tokens import Keyword
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Any, AsyncIterator

from fastmcp import FastMCP

from . import __version__
from .config import load_config, ServerConfig
from .security.sanitizer import SQLSanitizer
from .adapters.base import DatabaseAdapter
from .adapters.postgresql import PostgreSQLAdapter
from .adapters.sqlite import SQLiteAdapter
from .adapters.mysql import MySQLAdapter
from .adapters.duckdb import DuckDBAdapter

server_config: Optional[ServerConfig] = None
adapters: dict[str, DatabaseAdapter] = {}

_query_history: collections.deque = collections.deque(maxlen=100)
_schema_snapshots: dict[str, dict] = {}
_query_semaphore = asyncio.Semaphore(10)

_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "sys", "mysql", "performance_schema"}


class _TokenBucket:
    """Simple token-bucket rate limiter (requests per minute, with burst capacity)."""

    def __init__(self, rate_per_minute: int, burst: int) -> None:
        self.rate_per_second = rate_per_minute / 60.0
        self.capacity = max(burst, 1)
        self.tokens = float(self.capacity)
        self.last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


_rate_limiter: Optional[_TokenBucket] = None


def _create_adapter(db_config: Any) -> DatabaseAdapter:
    if db_config.type == "postgresql":
        return PostgreSQLAdapter(db_config)
    elif db_config.type == "sqlite":
        return SQLiteAdapter(db_config)
    elif db_config.type == "mysql":
        return MySQLAdapter(db_config)
    elif db_config.type == "duckdb":
        return DuckDBAdapter(db_config)
    raise ValueError(f"Unsupported database type: {db_config.type}")


async def _initialize_adapters(config: ServerConfig) -> None:
    global adapters
    for db_config in config.databases:
        try:
            adapter = _create_adapter(db_config)
            await adapter.connect()
            key = f"{db_config.type}:{db_config.database}"
            adapters[key] = adapter
            print(f"Connected to {db_config.type}:{db_config.database}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to connect to {db_config.type}:{db_config.database}: {e}", file=sys.stderr)


async def _cleanup_adapters() -> None:
    for adapter in adapters.values():
        try:
            await adapter.disconnect()
        except Exception as e:
            print(f"Error disconnecting adapter: {e}", file=sys.stderr)
    adapters.clear()


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    global server_config, _rate_limiter
    server_config = load_config()
    _rate_limiter = _TokenBucket(
        server_config.security.rate_limit_rpm, server_config.security.rate_limit_burst
    )
    if not server_config.databases:
        print("Warning: No databases configured. Set POSTGRES_URI, SQLITE_PATH, or MYSQL_URI.", file=sys.stderr)
    else:
        await _initialize_adapters(server_config)
    try:
        yield
    finally:
        await _cleanup_adapters()


mcp = FastMCP("Universal Database MCP", lifespan=lifespan)


def _get_adapter(database: Optional[str] = None) -> DatabaseAdapter:
    if not adapters:
        raise RuntimeError("No databases connected. Check server configuration.")

    if database:
        adapter = adapters.get(database)
        if not adapter:
            available = ", ".join(adapters.keys())
            raise ValueError(f"Database '{database}' not found. Available: {available}")
        return adapter

    if len(adapters) == 1:
        return next(iter(adapters.values()))

    available = ", ".join(adapters.keys())
    raise ValueError(
        f"Multiple databases configured. Specify 'database' param (format: 'type:name'). Available: {available}"
    )


def _error(msg: str, details: Optional[Any] = None, exc_type: str = "Error") -> str:
    payload: dict[str, Any] = {"error": msg, "type": exc_type}
    if details is not None:
        payload["details"] = details
    return json.dumps(payload, indent=2)


def _audit_log(event: str, **kwargs: Any) -> None:
    """Emit a structured JSON audit log entry to stderr."""
    entry = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    print(json.dumps(entry, default=str), file=sys.stderr)


def _extract_table_names(sql: str) -> List[str]:
    """Extract table names referenced after FROM/JOIN keywords."""
    tables: List[str] = []
    parsed = sqlparse.parse(sql)
    if not parsed:
        return tables

    next_is_table = False
    for token in parsed[0].flatten():
        if token.is_whitespace:
            continue
        if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
            next_is_table = True
            continue
        if next_is_table:
            if token.ttype is Keyword:
                next_is_table = False
                continue
            if token.ttype is None or str(token.ttype).startswith("Token.Name"):
                name = str(token.value).strip().strip('"').strip("`")
                if name:
                    tables.append(name)
            next_is_table = False

    return tables


@mcp.tool()
async def query(
    sql: str,
    params: Optional[List[Any]] = None,
    database: Optional[str] = None,
) -> str:
    """
    Execute a SQL query against the database.

    Supports parameterized queries for injection safety. In read-only mode, destructive
    operations (INSERT, UPDATE, DELETE, DROP, etc.) are blocked.

    Args:
        sql: SQL query to execute
        params: Optional list of parameters for parameterized queries (use instead of string formatting)
        database: Database key (format: "type:name"). Required when multiple databases are configured.

    Returns:
        JSON with rows, fields, row_count, and execution_time_ms.
    """
    cfg = server_config
    if cfg is None:
        return _error("Server not initialized")

    if _rate_limiter is not None and not await _rate_limiter.acquire():
        return _error(
            "Rate limit exceeded",
            [f"Limit: {cfg.security.rate_limit_rpm} requests/minute (burst {cfg.security.rate_limit_burst})"],
        )

    is_valid, errors = SQLSanitizer.validate_query(sql, cfg.security.allow_destructive)
    if not is_valid:
        return _error("Query validation failed", errors)

    if params:
        for p in params:
            if not isinstance(p, (str, int, float, bool, type(None))):
                return _error(
                    "Invalid parameter type",
                    ["Only string, number, boolean, and null are allowed as parameters"],
                )

    if cfg.security.whitelisted_tables:
        referenced = _extract_table_names(sql)
        allowed = {t.lower() for t in cfg.security.whitelisted_tables}
        blocked = [
            t for t in referenced
            if t.lower() not in allowed or t.lower().split(".")[0] in _SYSTEM_SCHEMAS
        ]
        if blocked:
            return _error("Table access denied", blocked)

    _, complexity_warnings = SQLSanitizer.check_complexity(sql, cfg.security.max_joins)

    try:
        adapter = _get_adapter(database)

        if cfg.security.dry_run:
            plan = await adapter.explain(sql, params)
            response = {
                "dry_run": True,
                "plan": plan.plan,
                "estimated_cost": plan.estimated_cost,
                "estimated_rows": plan.estimated_rows,
                "warning": "Dry-run mode enabled: query was not executed",
            }
            if complexity_warnings:
                response["complexity_warnings"] = complexity_warnings
            return json.dumps(response, indent=2, default=str)

        async with _query_semaphore:
            result = await adapter.query(sql, params)

        truncated = False
        if len(result.rows) > cfg.security.max_result_rows:
            result.rows = result.rows[: cfg.security.max_result_rows]
            truncated = True

        response = {
            "rows": result.rows,
            "row_count": result.row_count,
            "fields": result.fields,
            "execution_time_ms": round(result.execution_time_ms, 2),
        }
        if truncated:
            response["warning"] = f"Results truncated to {cfg.security.max_result_rows} rows"
        if complexity_warnings:
            response["complexity_warnings"] = complexity_warnings

        _query_history.append(
            {
                "sql": sql,
                "database": f"{adapter.get_type()}:{adapter.get_database()}",
                "execution_time_ms": round(result.execution_time_ms, 2),
                "row_count": result.row_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        if cfg.security.enable_logging:
            _audit_log(
                "query",
                database=f"{adapter.get_type()}:{adapter.get_database()}",
                execution_time_ms=round(result.execution_time_ms, 2),
                row_count=result.row_count,
                truncated=truncated,
            )

        return json.dumps(response, indent=2, default=str)
    except (ValueError, RuntimeError) as e:
        return _error(str(e), exc_type=type(e).__name__)
    except Exception as e:
        return _error(str(e), exc_type=type(e).__name__)


@mcp.tool()
async def schema(
    tables: Optional[List[str]] = None,
    database: Optional[str] = None,
) -> str:
    """
    Get database schema information: tables, columns, types, and constraints.

    Args:
        tables: Optional list of specific table names to inspect
        database: Database key (format: "type:name")

    Returns:
        JSON with list of tables and their column definitions.
    """
    try:
        adapter = _get_adapter(database)
        info = await adapter.get_schema(tables)
        return json.dumps(
            {
                "tables": [
                    {
                        "name": t.name,
                        "schema": t.schema,
                        "columns": t.columns,
                    }
                    for t in info.tables
                ]
            },
            indent=2,
        )
    except Exception as e:
        return _error(str(e), exc_type=type(e).__name__)


@mcp.tool()
async def explain(
    sql: str,
    params: Optional[List[Any]] = None,
    database: Optional[str] = None,
) -> str:
    """
    Get query execution plan without running the query.

    Args:
        sql: SQL query to analyze
        params: Optional parameters for the query
        database: Database key (format: "type:name")

    Returns:
        JSON with plan, estimated_cost, and estimated_rows.
    """
    cfg = server_config
    if cfg is None:
        return _error("Server not initialized")

    # EXPLAIN never needs destructive operations — always validate read-only.
    is_valid, errors = SQLSanitizer.validate_query(sql, allow_destructive=False)
    if not is_valid:
        return _error("Query validation failed", errors)

    try:
        adapter = _get_adapter(database)
        plan = await adapter.explain(sql, params)
        return json.dumps(
            {
                "plan": plan.plan,
                "estimated_cost": plan.estimated_cost,
                "estimated_rows": plan.estimated_rows,
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error(str(e), exc_type=type(e).__name__)


@mcp.tool()
async def health(database: Optional[str] = None) -> str:
    """
    Check database connection health and get server version info.

    Args:
        database: Database key (format: "type:name")

    Returns:
        JSON with connected, response_time_ms, version, and error (if any).
    """
    try:
        adapter = _get_adapter(database)
        status = await adapter.health()
        return json.dumps(
            {
                "connected": status.connected,
                "response_time_ms": round(status.response_time_ms, 2),
                "version": status.version,
                "error": status.error,
                "pool_size": status.pool_size,
                "pool_idle": status.pool_idle,
            },
            indent=2,
        )
    except Exception as e:
        return _error(str(e), exc_type=type(e).__name__)


@mcp.tool()
async def query_history(limit: int = 10) -> str:
    """
    Get recent query execution history (most recent first).

    Args:
        limit: Maximum number of history entries to return (default 10)

    Returns:
        JSON list of recent queries with sql, database, execution_time_ms, row_count, timestamp.
    """
    entries = list(_query_history)[-limit:]
    entries.reverse()
    return json.dumps({"history": entries}, indent=2, default=str)


async def _get_table_columns(database: Optional[str] = None) -> dict:
    """Build a {table_name: {col_name: col_type}} map from the live schema."""
    adapter = _get_adapter(database)
    info = await adapter.get_schema()
    snapshot: dict[str, dict[str, str]] = {}
    for table in info.tables:
        snapshot[table.name] = {col["name"]: col["type"] for col in table.columns}
    return snapshot


@mcp.tool()
async def snapshot_schema(database: Optional[str] = None) -> str:
    """
    Take a snapshot of the current database schema for later drift detection.

    Args:
        database: Database key (format: "type:name")

    Returns:
        JSON confirming the snapshot was stored, with table count.
    """
    try:
        adapter = _get_adapter(database)
        key = f"{adapter.get_type()}:{adapter.get_database()}"
        snapshot = await _get_table_columns(database)
        _schema_snapshots[key] = snapshot
        return json.dumps({"database": key, "tables_snapshotted": len(snapshot)}, indent=2)
    except Exception as e:
        return _error(str(e), exc_type=type(e).__name__)


@mcp.tool()
async def schema_diff(database: Optional[str] = None) -> str:
    """
    Compare the current schema against the last snapshot taken with snapshot_schema.

    Args:
        database: Database key (format: "type:name")

    Returns:
        JSON describing tables/columns added, dropped, or with changed types since the snapshot.
    """
    try:
        adapter = _get_adapter(database)
        key = f"{adapter.get_type()}:{adapter.get_database()}"
        if key not in _schema_snapshots:
            return _error("No snapshot found for this database", ["Call snapshot_schema first"])

        previous = _schema_snapshots[key]
        current = await _get_table_columns(database)

        added_tables = sorted(set(current) - set(previous))
        dropped_tables = sorted(set(previous) - set(current))

        column_changes: dict[str, dict[str, Any]] = {}
        for table in set(current) & set(previous):
            prev_cols = previous[table]
            curr_cols = current[table]
            added_cols = sorted(set(curr_cols) - set(prev_cols))
            dropped_cols = sorted(set(prev_cols) - set(curr_cols))
            type_changed = {
                col: {"from": prev_cols[col], "to": curr_cols[col]}
                for col in set(prev_cols) & set(curr_cols)
                if prev_cols[col] != curr_cols[col]
            }
            if added_cols or dropped_cols or type_changed:
                column_changes[table] = {
                    "added_columns": added_cols,
                    "dropped_columns": dropped_cols,
                    "type_changed": type_changed,
                }

        return json.dumps(
            {
                "database": key,
                "added_tables": added_tables,
                "dropped_tables": dropped_tables,
                "column_changes": column_changes,
            },
            indent=2,
        )
    except Exception as e:
        return _error(str(e), exc_type=type(e).__name__)


@mcp.tool()
async def list_databases() -> str:
    """
    List all configured databases and their connection status.

    Returns:
        JSON with list of databases including key, type, database name, and connection status.
    """
    return json.dumps(
        {
            "databases": [
                {
                    "key": key,
                    "type": adapter.get_type(),
                    "database": adapter.get_database(),
                    "connected": adapter.is_connected(),
                }
                for key, adapter in adapters.items()
            ]
        },
        indent=2,
    )


async def _run_check() -> int:
    """Validate config and test connectivity to all configured databases."""
    config = load_config()

    if not config.databases:
        print("No databases configured.", file=sys.stderr)
        return 1

    all_ok = True
    for db_config in config.databases:
        label = f"{db_config.type}:{db_config.database}"
        adapter = _create_adapter(db_config)
        try:
            await adapter.connect()
            status = await adapter.health()
            if status.connected:
                print(f"✅ {label}: connected ({status.response_time_ms:.2f}ms)")
            else:
                print(f"❌ {label}: {status.error}")
                all_ok = False
        except Exception as e:
            print(f"❌ {label}: {e}")
            all_ok = False
        finally:
            try:
                await adapter.disconnect()
            except Exception:
                pass

    return 0 if all_ok else 1


def main() -> None:
    """Entry point for the MCP server."""
    parser = argparse.ArgumentParser(prog="universal-db-mcp")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument(
        "--check", action="store_true", help="Validate config and test database connections"
    )
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    if args.check:
        exit_code = asyncio.run(_run_check())
        sys.exit(exit_code)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
