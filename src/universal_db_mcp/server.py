"""Main FastMCP server for Universal Database MCP."""

import sys
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Any, AsyncIterator

from fastmcp import FastMCP

from .config import load_config, ServerConfig
from .security.sanitizer import SQLSanitizer
from .adapters.base import DatabaseAdapter
from .adapters.postgresql import PostgreSQLAdapter
from .adapters.sqlite import SQLiteAdapter
from .adapters.mysql import MySQLAdapter

server_config: Optional[ServerConfig] = None
adapters: dict[str, DatabaseAdapter] = {}


def _create_adapter(db_config: Any) -> DatabaseAdapter:
    if db_config.type == "postgresql":
        return PostgreSQLAdapter(db_config)
    elif db_config.type == "sqlite":
        return SQLiteAdapter(db_config)
    elif db_config.type == "mysql":
        return MySQLAdapter(db_config)
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
    global server_config
    server_config = load_config()
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

    try:
        adapter = _get_adapter(database)
        result = await adapter.query(sql, params)

        truncated = False
        if len(result.rows) > cfg.security.max_result_rows:
            result.rows = result.rows[: cfg.security.max_result_rows]
            truncated = True

        response: dict[str, Any] = {
            "rows": result.rows,
            "row_count": result.row_count,
            "fields": result.fields,
            "execution_time_ms": round(result.execution_time_ms, 2),
        }
        if truncated:
            response["warning"] = f"Results truncated to {cfg.security.max_result_rows} rows"

        if cfg.security.enable_logging:
            print(
                f"Query on {adapter.get_type()}:{adapter.get_database()} "
                f"in {result.execution_time_ms:.2f}ms",
                file=sys.stderr,
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


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
