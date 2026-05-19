"""DuckDB database adapter — columnar analytics, zero-infra, in-memory or file-based."""

import time
import asyncio
import duckdb
from typing import List, Optional, Any

from .base import DatabaseAdapter, QueryResult, SchemaInfo, TableInfo, ExplainResult, HealthStatus
from ..config import DatabaseConfig
from ..security.sanitizer import SQLSanitizer


class DuckDBAdapter(DatabaseAdapter):
    """
    DuckDB adapter using the native duckdb Python package.

    DuckDB connections are not thread-safe, so all operations run in a thread
    pool executor behind an asyncio.Lock to ensure single-threaded access.
    Read-only mode is enforced at the engine level via duckdb.connect(read_only=True).
    """

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._lock = asyncio.Lock()

    async def _run(self, func):
        """Run a synchronous function in the default thread pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)

    async def connect(self) -> None:
        db_path = self.config.database
        read_only = self.config.read_only

        def _connect():
            return duckdb.connect(database=db_path, read_only=read_only)

        self._conn = await self._run(_connect)
        self.connected = True

    async def disconnect(self) -> None:
        if self._conn:
            conn = self._conn

            def _close():
                conn.close()

            await self._run(_close)
            self._conn = None
        self.connected = False

    async def query(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        if not self._conn:
            raise RuntimeError("Database not connected")

        conn = self._conn
        start = time.monotonic()

        async with self._lock:
            def _exec():
                result = conn.execute(sql, params or [])
                rows = result.fetchall()
                desc = result.description
                return rows, desc

            rows_raw, description = await self._run(_exec)

        elapsed = (time.monotonic() - start) * 1000

        fields: List[dict] = []
        if description:
            fields = [{"name": d[0], "type": str(d[1]) if d[1] else "unknown"} for d in description]

        col_names = [f["name"] for f in fields]
        result_rows = [dict(zip(col_names, row)) for row in rows_raw]

        return QueryResult(
            rows=result_rows,
            row_count=len(result_rows),
            fields=fields,
            execution_time_ms=elapsed,
        )

    async def get_schema(self, table_names: Optional[List[str]] = None) -> SchemaInfo:
        if not self._conn:
            raise RuntimeError("Database not connected")

        conn = self._conn

        async with self._lock:
            def _get_tables():
                if table_names:
                    safe_names = [SQLSanitizer.sanitize_identifier(t) for t in table_names]
                    placeholders = ",".join("?" * len(safe_names))
                    return conn.execute(
                        f"SELECT table_name FROM information_schema.tables "
                        f"WHERE table_schema='main' AND table_name IN ({placeholders})",
                        safe_names,
                    ).fetchall()
                return conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                ).fetchall()

            tables_raw = await self._run(_get_tables)
            tnames = [r[0] for r in tables_raw]

            schema_tables: List[TableInfo] = []
            for tname in tnames:
                safe = SQLSanitizer.sanitize_identifier(tname)

                def _get_cols(name=safe):
                    return conn.execute(
                        "SELECT column_name, data_type, is_nullable "
                        "FROM information_schema.columns "
                        "WHERE table_schema='main' AND table_name=?",
                        [name],
                    ).fetchall()

                cols = await self._run(_get_cols)
                schema_tables.append(
                    TableInfo(
                        name=tname,
                        columns=[
                            {"name": c[0], "type": c[1], "nullable": c[2] == "YES"}
                            for c in cols
                        ],
                    )
                )

        return SchemaInfo(tables=schema_tables)

    async def explain(self, sql: str, params: Optional[List[Any]] = None) -> ExplainResult:
        if not self._conn:
            raise RuntimeError("Database not connected")

        conn = self._conn

        async with self._lock:
            def _explain():
                result = conn.execute(f"EXPLAIN {sql}", params or [])
                rows = result.fetchall()
                return "\n".join(
                    str(r[1]) if len(r) > 1 else str(r[0]) for r in rows
                )

            plan = await self._run(_explain)

        return ExplainResult(plan=plan)

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            if not self._conn:
                return HealthStatus(connected=False, response_time_ms=0, error="Not initialized")

            conn = self._conn

            def _version():
                return conn.execute("SELECT version()").fetchone()[0]

            version_str = await self._run(_version)
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                connected=True,
                response_time_ms=elapsed,
                version=f"DuckDB {version_str}",
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=False, response_time_ms=elapsed, error=str(e))
