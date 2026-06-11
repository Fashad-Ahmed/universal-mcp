"""Drives the real MCP server tools against demo.db for the README demo recording."""

import asyncio
import json

from src.universal_db_mcp.config import DatabaseConfig, SecurityConfig, ServerConfig
from src.universal_db_mcp.adapters.sqlite import SQLiteAdapter
import src.universal_db_mcp.server as server


async def setup(dry_run: bool = False) -> SQLiteAdapter:
    config = DatabaseConfig(type="sqlite", database="./demo.db", read_only=True)
    adapter = SQLiteAdapter(config)
    await adapter.connect()
    server.adapters.clear()
    server.adapters["sqlite:./demo.db"] = adapter
    server.server_config = ServerConfig(
        security=SecurityConfig(
            allow_destructive=False,
            enable_logging=False,
            dry_run=dry_run,
        )
    )
    return adapter


SUM_QUERY = (
    "SELECT c.name, SUM(o.amount) AS total_spent "
    "FROM customers c JOIN orders o ON o.customer_id = c.id "
    "WHERE o.created_at LIKE '2026-05%' "
    "GROUP BY c.id ORDER BY total_spent DESC"
)


async def run_schema() -> None:
    adapter = await setup()
    raw = await server.schema()
    print(json.dumps(json.loads(raw), indent=2))
    await adapter.disconnect()


async def run_query() -> None:
    adapter = await setup()
    raw = await server.query(SUM_QUERY)
    print(json.dumps(json.loads(raw), indent=2))
    await adapter.disconnect()


async def run_blocked() -> None:
    adapter = await setup()
    raw = await server.query("DROP TABLE customers")
    print(json.dumps(json.loads(raw), indent=2))
    await adapter.disconnect()


async def run_dry_run() -> None:
    adapter = await setup(dry_run=True)
    raw = await server.query(SUM_QUERY)
    print(json.dumps(json.loads(raw), indent=2))
    await adapter.disconnect()


if __name__ == "__main__":
    import sys

    asyncio.run(
        {
            "schema": run_schema,
            "query": run_query,
            "blocked": run_blocked,
            "dry_run": run_dry_run,
        }[sys.argv[1]]()
    )
