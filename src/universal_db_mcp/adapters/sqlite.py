"""SQLite database adapter using aiosqlite."""

import time
import aiosqlite
from typing import List, Dict, Any, Optional

from .base import DatabaseAdapter, QueryResult, SchemaInfo, TableInfo, ExplainResult, HealthStatus
from ..config import DatabaseConfig


class SQLiteAdapter(DatabaseAdapter):
    """SQLite adapter using aiosqlite."""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        db_path = self.config.database

        if db_path == ":memory:":
            self.db = await aiosqlite.connect(":memory:", timeout=float(self.config.query_timeout))
        elif self.config.read_only:
            uri = f"file:{db_path}?mode=ro"
            self.db = await aiosqlite.connect(
                uri, uri=True, timeout=float(self.config.query_timeout)
            )
        else:
            self.db = await aiosqlite.connect(db_path, timeout=float(self.config.query_timeout))

        self.db.row_factory = aiosqlite.Row
        self.connected = True

    async def disconnect(self) -> None:
        if self.db:
            await self.db.close()
            self.db = None
        self.connected = False

    async def query(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        if not self.db:
            raise RuntimeError("Database not connected")

        start = time.monotonic()
        async with self.db.execute(sql, params or []) as cursor:
            rows_raw = await cursor.fetchall()
            elapsed = (time.monotonic() - start) * 1000

            result_rows = [dict(r) for r in rows_raw]
            fields: List[Dict[str, str]] = []
            if cursor.description:
                fields = [{"name": d[0], "type": "unknown"} for d in cursor.description]

        if not self.config.read_only:
            await self.db.commit()

        return QueryResult(
            rows=result_rows,
            row_count=len(result_rows),
            fields=fields,
            execution_time_ms=elapsed,
        )

    async def get_schema(self, table_names: Optional[List[str]] = None) -> SchemaInfo:
        if not self.db:
            raise RuntimeError("Database not connected")

        if table_names:
            placeholders = ",".join("?" * len(table_names))
            # placeholders is a fixed "?,?,..." string; actual table names
            # are bound as parameters below, not interpolated.
            q = f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})"  # nosec B608
            async with self.db.execute(q, table_names) as cur:
                tables_raw = await cur.fetchall()
        else:
            async with self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ) as cur:
                tables_raw = await cur.fetchall()

        schema_tables: List[TableInfo] = []
        for row in tables_raw:
            tname = row[0]
            async with self.db.execute(f"PRAGMA table_info({tname})") as cur:
                cols_raw = await cur.fetchall()

            schema_tables.append(
                TableInfo(
                    name=tname,
                    columns=[
                        {
                            "name": c[1],
                            "type": c[2],
                            "nullable": c[3] == 0,
                            "default": c[4],
                            "primary_key": c[5] == 1,
                        }
                        for c in cols_raw
                    ],
                )
            )

        return SchemaInfo(tables=schema_tables)

    async def explain(self, sql: str, params: Optional[List[Any]] = None) -> ExplainResult:
        if not self.db:
            raise RuntimeError("Database not connected")

        async with self.db.execute(f"EXPLAIN QUERY PLAN {sql}", params or []) as cur:
            plan_rows = await cur.fetchall()

        return ExplainResult(plan=str([dict(r) for r in plan_rows]))

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            if not self.db:
                return HealthStatus(connected=False, response_time_ms=0, error="Not initialized")

            async with self.db.execute("SELECT sqlite_version()") as cur:
                row = await cur.fetchone()
            version = f"SQLite {row[0]}" if row else "SQLite unknown"
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=True, response_time_ms=elapsed, version=version)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=False, response_time_ms=elapsed, error=str(e))
