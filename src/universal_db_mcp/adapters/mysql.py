"""MySQL database adapter using aiomysql."""

import time
import aiomysql
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from .base import DatabaseAdapter, QueryResult, SchemaInfo, TableInfo, ExplainResult, HealthStatus
from ..config import DatabaseConfig


class MySQLAdapter(DatabaseAdapter):
    """MySQL adapter using aiomysql connection pooling."""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.pool: Optional[aiomysql.Pool] = None

    def _conn_kwargs(self) -> Dict[str, Any]:
        if self.config.connection_string:
            parsed = urlparse(self.config.connection_string)
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 3306,
                "user": parsed.username or "root",
                "password": parsed.password or "",
                "db": parsed.path.lstrip("/") if parsed.path else self.config.database,
            }
        return {
            "host": self.config.host or "localhost",
            "port": self.config.port or 3306,
            "user": self.config.username or "root",
            "password": self.config.password or "",
            "db": self.config.database,
        }

    async def connect(self) -> None:
        kwargs = self._conn_kwargs()
        self.pool = await aiomysql.create_pool(
            **kwargs,
            minsize=1,
            maxsize=self.config.max_connections,
            connect_timeout=self.config.query_timeout,
            autocommit=True,
        )
        self.connected = True

    async def disconnect(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
        self.connected = False

    async def query(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        if not self.pool:
            raise RuntimeError("Database not connected")

        start = time.monotonic()
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params or [])
                rows = list(await cur.fetchall())
                elapsed = (time.monotonic() - start) * 1000
                fields: List[Dict[str, str]] = []
                if cur.description:
                    fields = [{"name": d[0], "type": "unknown"} for d in cur.description]

        return QueryResult(
            rows=rows,
            row_count=len(rows),
            fields=fields,
            execution_time_ms=elapsed,
        )

    async def get_schema(self, table_names: Optional[List[str]] = None) -> SchemaInfo:
        if not self.pool:
            raise RuntimeError("Database not connected")

        where_extra = ""
        params: List[Any] = []
        if table_names:
            placeholders = ",".join(["%s"] * len(table_names))
            where_extra = f"AND TABLE_NAME IN ({placeholders})"
            params.extend(table_names)

        # where_extra contains only fixed "%s" placeholders; actual table
        # names are bound as parameters below, not interpolated.
        sql_lines = [
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY",
            "FROM INFORMATION_SCHEMA.COLUMNS",
            "WHERE TABLE_SCHEMA = DATABASE()",
            where_extra,
            "ORDER BY TABLE_NAME, ORDINAL_POSITION",
        ]
        sql = "\n".join(sql_lines)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                rows = list(await cur.fetchall())

        tables_dict: Dict[str, TableInfo] = {}
        for row in rows:
            tname = row["TABLE_NAME"]
            if tname not in tables_dict:
                tables_dict[tname] = TableInfo(name=tname, columns=[])
            tables_dict[tname].columns.append(
                {
                    "name": row["COLUMN_NAME"],
                    "type": row["DATA_TYPE"],
                    "nullable": row["IS_NULLABLE"] == "YES",
                    "default": row["COLUMN_DEFAULT"],
                    "primary_key": row["COLUMN_KEY"] == "PRI",
                }
            )

        return SchemaInfo(tables=list(tables_dict.values()))

    async def explain(self, sql: str, params: Optional[List[Any]] = None) -> ExplainResult:
        if not self.pool:
            raise RuntimeError("Database not connected")

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"EXPLAIN FORMAT=JSON {sql}", params or [])
                row = await cur.fetchone()

        return ExplainResult(plan=str(row[0]) if row else "No plan available")

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            if not self.pool:
                return HealthStatus(connected=False, response_time_ms=0, error="Pool not initialized")

            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT VERSION()")
                    row = await cur.fetchone()
            version = str(row[0]) if row else "Unknown"
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=True, response_time_ms=elapsed, version=version)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=False, response_time_ms=elapsed, error=str(e))
