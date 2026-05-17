"""Database adapter integration tests. PostgreSQL/MySQL require env vars to run."""

import os
import pytest
import pytest_asyncio

from src.universal_db_mcp.config import DatabaseConfig
from src.universal_db_mcp.adapters.sqlite import SQLiteAdapter
from src.universal_db_mcp.adapters.postgresql import PostgreSQLAdapter
from src.universal_db_mcp.adapters.mysql import MySQLAdapter


# ─── SQLite Adapter ───────────────────────────────────────────────────────────

class TestSQLiteConnect:
    @pytest.mark.asyncio
    async def test_in_memory_connect(self):
        config = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
        async with SQLiteAdapter(config) as adapter:
            assert adapter.connected

    @pytest.mark.asyncio
    async def test_disconnect_sets_flag(self):
        config = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
        adapter = SQLiteAdapter(config)
        await adapter.connect()
        assert adapter.connected
        await adapter.disconnect()
        assert not adapter.connected

    @pytest.mark.asyncio
    async def test_file_db_connect(self, tmp_db):
        config = DatabaseConfig(type="sqlite", database=tmp_db, read_only=False)
        async with SQLiteAdapter(config) as adapter:
            assert adapter.connected

    @pytest.mark.asyncio
    async def test_readonly_file_db(self, tmp_db):
        # Create the file first
        config_rw = DatabaseConfig(type="sqlite", database=tmp_db, read_only=False)
        async with SQLiteAdapter(config_rw) as adapter:
            await adapter.query("CREATE TABLE t (x INT)")

        config_ro = DatabaseConfig(type="sqlite", database=tmp_db, read_only=True)
        async with SQLiteAdapter(config_ro) as adapter:
            assert adapter.connected


class TestSQLiteQuery:
    @pytest.mark.asyncio
    async def test_select_one(self, memory_adapter):
        result = await memory_adapter.query("SELECT 1 AS val")
        assert result.rows[0]["val"] == 1
        assert result.row_count == 1

    @pytest.mark.asyncio
    async def test_create_table(self, memory_adapter):
        result = await memory_adapter.query("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        assert result.row_count == 0

    @pytest.mark.asyncio
    async def test_insert_and_select(self, memory_adapter):
        await memory_adapter.query("CREATE TABLE items (id INTEGER, name TEXT)")
        await memory_adapter.query("INSERT INTO items VALUES (?, ?)", [1, "widget"])
        result = await memory_adapter.query("SELECT * FROM items")
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "widget"

    @pytest.mark.asyncio
    async def test_parameterized_query(self, memory_adapter_with_data):
        result = await memory_adapter_with_data.query(
            "SELECT * FROM users WHERE name = ?", ["Alice"]
        )
        assert len(result.rows) == 1
        assert result.rows[0]["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_fields_populated(self, memory_adapter_with_data):
        result = await memory_adapter_with_data.query("SELECT id, name FROM users LIMIT 1")
        field_names = [f["name"] for f in result.fields]
        assert "id" in field_names
        assert "name" in field_names

    @pytest.mark.asyncio
    async def test_execution_time_positive(self, memory_adapter):
        result = await memory_adapter.query("SELECT 1")
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_result(self, memory_adapter_with_data):
        result = await memory_adapter_with_data.query(
            "SELECT * FROM users WHERE id = ?", [999]
        )
        assert result.rows == []
        assert result.row_count == 0


class TestSQLiteSchema:
    @pytest.mark.asyncio
    async def test_get_schema_empty(self, memory_adapter):
        info = await memory_adapter.get_schema()
        assert info.tables == []

    @pytest.mark.asyncio
    async def test_get_schema_with_tables(self, memory_adapter_with_data):
        info = await memory_adapter_with_data.get_schema()
        names = [t.name for t in info.tables]
        assert "users" in names

    @pytest.mark.asyncio
    async def test_get_schema_columns(self, memory_adapter_with_data):
        info = await memory_adapter_with_data.get_schema(["users"])
        users_table = next(t for t in info.tables if t.name == "users")
        col_names = [c["name"] for c in users_table.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names

    @pytest.mark.asyncio
    async def test_get_schema_filter_by_table(self, memory_adapter):
        await memory_adapter.query("CREATE TABLE a (x INT)")
        await memory_adapter.query("CREATE TABLE b (y TEXT)")
        info = await memory_adapter.get_schema(["a"])
        assert len(info.tables) == 1
        assert info.tables[0].name == "a"


class TestSQLiteExplain:
    @pytest.mark.asyncio
    async def test_explain_returns_plan(self, memory_adapter_with_data):
        result = await memory_adapter_with_data.explain("SELECT * FROM users WHERE id = ?", [1])
        assert isinstance(result.plan, str)
        assert len(result.plan) > 0


class TestSQLiteHealth:
    @pytest.mark.asyncio
    async def test_health_connected(self, memory_adapter):
        status = await memory_adapter.health()
        assert status.connected
        assert status.version is not None
        assert "SQLite" in status.version
        assert status.error is None

    @pytest.mark.asyncio
    async def test_health_disconnected(self):
        config = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
        adapter = SQLiteAdapter(config)
        # Don't connect
        status = await adapter.health()
        assert not status.connected
        assert status.error is not None


# ─── PostgreSQL Adapter (skipped without env var) ─────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_DSN"),
    reason="TEST_POSTGRES_DSN not set",
)
class TestPostgreSQLAdapter:
    @pytest_asyncio.fixture
    async def pg_adapter(self):
        config = DatabaseConfig(
            type="postgresql",
            database="test",
            connection_string=os.environ["TEST_POSTGRES_DSN"],
            read_only=False,
            query_timeout=10,
        )
        adapter = PostgreSQLAdapter(config)
        await adapter.connect()
        await adapter.query("CREATE SCHEMA IF NOT EXISTS mcp_test")
        yield adapter
        await adapter.query("DROP SCHEMA IF EXISTS mcp_test CASCADE")
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_select_one(self, pg_adapter):
        result = await pg_adapter.query("SELECT 1 AS val")
        assert result.rows[0]["val"] == 1

    @pytest.mark.asyncio
    async def test_create_and_insert(self, pg_adapter):
        await pg_adapter.query("CREATE TABLE mcp_test.items (id SERIAL, name TEXT)")
        result = await pg_adapter.query(
            "INSERT INTO mcp_test.items (name) VALUES ($1)", ["hello"]
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_schema_introspection(self, pg_adapter):
        await pg_adapter.query(
            "CREATE TABLE mcp_test.pg_cols (id INT PRIMARY KEY, label VARCHAR(100))"
        )
        info = await pg_adapter.get_schema(["pg_cols"])
        assert len(info.tables) > 0

    @pytest.mark.asyncio
    async def test_health(self, pg_adapter):
        status = await pg_adapter.health()
        assert status.connected
        assert "PostgreSQL" in (status.version or "")


# ─── MySQL Adapter (skipped without env var) ──────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("TEST_MYSQL_DSN"),
    reason="TEST_MYSQL_DSN not set",
)
class TestMySQLAdapter:
    @pytest_asyncio.fixture
    async def mysql_adapter(self):
        config = DatabaseConfig(
            type="mysql",
            database="test",
            connection_string=os.environ["TEST_MYSQL_DSN"],
            read_only=False,
            query_timeout=10,
        )
        adapter = MySQLAdapter(config)
        await adapter.connect()
        yield adapter
        await adapter.query("DROP TABLE IF EXISTS mcp_test_items")
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_select_one(self, mysql_adapter):
        result = await mysql_adapter.query("SELECT 1 AS val")
        assert result.rows[0]["val"] == 1

    @pytest.mark.asyncio
    async def test_health(self, mysql_adapter):
        status = await mysql_adapter.health()
        assert status.connected
