"""PostgreSQL database adapter using asyncpg."""

import time
import asyncpg
from typing import List, Dict, Any, Optional

from .base import DatabaseAdapter, QueryResult, SchemaInfo, TableInfo, ExplainResult, HealthStatus
from ..config import DatabaseConfig


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL adapter using asyncpg connection pooling."""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.pool: Optional[asyncpg.Pool] = None

    def _build_dsn(self) -> str:
        if self.config.connection_string:
            return self.config.connection_string
        user = self.config.username or ""
        password = self.config.password or ""
        host = self.config.host or "localhost"
        port = self.config.port or 5432
        db = self.config.database
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    async def connect(self) -> None:
        dsn = self._build_dsn()
        ssl_ctx: Any = "require" if self.config.ssl else None

        async def _init_conn(conn: asyncpg.Connection) -> None:
            if self.config.read_only:
                await conn.execute(
                    "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"
                )

        self.pool = await asyncpg.create_pool(
            dsn=dsn,
            ssl=ssl_ctx,
            min_size=1,
            max_size=self.config.max_connections,
            command_timeout=float(self.config.query_timeout),
            init=_init_conn,
        )
        self.connected = True

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
        self.connected = False

    async def query(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        if not self.pool:
            raise RuntimeError("Database not connected")

        start = time.monotonic()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *(params or []))

        elapsed = (time.monotonic() - start) * 1000
        result_rows = [dict(r) for r in rows]
        fields = (
            [{"name": k, "type": type(rows[0][k]).__name__} for k in rows[0].keys()]
            if rows
            else []
        )
        return QueryResult(
            rows=result_rows,
            row_count=len(result_rows),
            fields=fields,
            execution_time_ms=elapsed,
        )

    async def get_schema(self, table_names: Optional[List[str]] = None) -> SchemaInfo:
        if not self.pool:
            raise RuntimeError("Database not connected")

        where_extra = ""
        params: List[Any] = []
        if table_names:
            where_extra = "AND t.tablename = ANY($1::text[])"
            params.append(table_names)

        sql = f"""
        SELECT
            t.schemaname,
            t.tablename,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            CASE WHEN tc.constraint_type = 'PRIMARY KEY' THEN true ELSE false END AS is_primary
        FROM pg_tables t
        JOIN information_schema.columns c
            ON t.tablename = c.table_name AND t.schemaname = c.table_schema
        LEFT JOIN information_schema.key_column_usage kcu
            ON c.table_schema = kcu.table_schema
            AND c.table_name = kcu.table_name
            AND c.column_name = kcu.column_name
        LEFT JOIN information_schema.table_constraints tc
            ON kcu.constraint_name = tc.constraint_name
            AND kcu.table_schema = tc.table_schema
        WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
            {where_extra}
        ORDER BY t.tablename, c.ordinal_position
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        tables_dict: Dict[str, TableInfo] = {}
        for row in rows:
            tname = row["tablename"]
            if tname not in tables_dict:
                tables_dict[tname] = TableInfo(
                    name=tname, schema=row["schemaname"], columns=[]
                )
            tables_dict[tname].columns.append(
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "primary_key": row["is_primary"],
                }
            )

        return SchemaInfo(tables=list(tables_dict.values()))

    async def explain(self, sql: str, params: Optional[List[Any]] = None) -> ExplainResult:
        if not self.pool:
            raise RuntimeError("Database not connected")

        explain_sql = f"EXPLAIN (FORMAT JSON, ANALYZE FALSE) {sql}"
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(explain_sql, *(params or []))

        plan_data = result[0] if result else {}
        plan_node = plan_data.get("Plan", {}) if isinstance(plan_data, dict) else {}
        return ExplainResult(
            plan=str(plan_data),
            estimated_cost=plan_node.get("Total Cost"),
            estimated_rows=plan_node.get("Plan Rows"),
        )

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            if not self.pool:
                return HealthStatus(connected=False, response_time_ms=0, error="Pool not initialized")

            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=True, response_time_ms=elapsed, version=str(version))
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(connected=False, response_time_ms=elapsed, error=str(e))
