"""Integration tests for FastMCP server tools using SQLite in-memory."""

import json
import pytest
import pytest_asyncio

from src.universal_db_mcp.config import DatabaseConfig, SecurityConfig, ServerConfig
from src.universal_db_mcp.adapters.sqlite import SQLiteAdapter
import src.universal_db_mcp.server as server


@pytest_asyncio.fixture
async def adapter_with_data():
    """Provide a connected in-memory SQLite adapter seeded with test data."""
    config = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
    adapter = SQLiteAdapter(config)
    await adapter.connect()
    await adapter.query("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    await adapter.query("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")
    await adapter.query("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com')")
    yield adapter
    await adapter.disconnect()


@pytest_asyncio.fixture
async def server_with_sqlite(adapter_with_data):
    """Inject adapter into server globals and configure server_config."""
    server.adapters["sqlite::memory:"] = adapter_with_data
    server.server_config = ServerConfig(
        security=SecurityConfig(
            allow_destructive=True,
            max_result_rows=1000,
            enable_logging=False,
        )
    )
    yield
    # conftest autouse fixture handles cleanup


class TestQueryTool:
    @pytest.mark.asyncio
    async def test_basic_select(self, server_with_sqlite):
        raw = await server.query("SELECT * FROM users ORDER BY id")
        result = json.loads(raw)
        assert "error" not in result
        assert len(result["rows"]) == 2
        assert result["rows"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_parameterized_query(self, server_with_sqlite):
        raw = await server.query("SELECT * FROM users WHERE id = ?", params=[1])
        result = json.loads(raw)
        assert result["rows"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_returns_fields(self, server_with_sqlite):
        raw = await server.query("SELECT id, name FROM users LIMIT 1")
        result = json.loads(raw)
        field_names = [f["name"] for f in result["fields"]]
        assert "id" in field_names
        assert "name" in field_names

    @pytest.mark.asyncio
    async def test_returns_execution_time(self, server_with_sqlite):
        raw = await server.query("SELECT 1")
        result = json.loads(raw)
        assert "execution_time_ms" in result

    @pytest.mark.asyncio
    async def test_destructive_blocked_in_readonly(self, adapter_with_data):
        config = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = ServerConfig(
            security=SecurityConfig(allow_destructive=False, enable_logging=False)
        )
        raw = await server.query("DROP TABLE users")
        result = json.loads(raw)
        assert "error" in result
        assert "validation" in result["error"].lower() or "details" in result

    @pytest.mark.asyncio
    async def test_union_select_blocked(self, server_with_sqlite):
        raw = await server.query("SELECT * FROM users UNION SELECT * FROM users")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_param_type_blocked(self, server_with_sqlite):
        raw = await server.query("SELECT * FROM users WHERE id = ?", params=[{"evil": "dict"}])
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_result_truncation(self, adapter_with_data):
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = ServerConfig(
            security=SecurityConfig(
                allow_destructive=True,
                max_result_rows=1,
                enable_logging=False,
            )
        )
        raw = await server.query("SELECT * FROM users")
        result = json.loads(raw)
        assert len(result["rows"]) == 1
        assert "warning" in result

    @pytest.mark.asyncio
    async def test_no_adapters_returns_error(self):
        server.server_config = ServerConfig(
            security=SecurityConfig(allow_destructive=True, enable_logging=False)
        )
        # adapters is empty from reset fixture
        raw = await server.query("SELECT 1")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_server_not_initialized_returns_error(self, adapter_with_data):
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = None
        raw = await server.query("SELECT 1")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_wrong_database_key_returns_error(self, server_with_sqlite):
        raw = await server.query("SELECT 1", database="nonexistent:db")
        result = json.loads(raw)
        assert "error" in result


class TestSchemaTool:
    @pytest.mark.asyncio
    async def test_lists_tables(self, server_with_sqlite):
        raw = await server.schema()
        result = json.loads(raw)
        assert "tables" in result
        names = [t["name"] for t in result["tables"]]
        assert "users" in names

    @pytest.mark.asyncio
    async def test_schema_has_columns(self, server_with_sqlite):
        raw = await server.schema(tables=["users"])
        result = json.loads(raw)
        users = next(t for t in result["tables"] if t["name"] == "users")
        col_names = [c["name"] for c in users["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names

    @pytest.mark.asyncio
    async def test_no_adapters_returns_error(self):
        server.server_config = ServerConfig(security=SecurityConfig())
        raw = await server.schema()
        result = json.loads(raw)
        assert "error" in result


class TestExplainTool:
    @pytest.mark.asyncio
    async def test_explain_returns_plan(self, server_with_sqlite):
        raw = await server.explain("SELECT * FROM users WHERE id = ?", params=[1])
        result = json.loads(raw)
        assert "plan" in result
        assert result["plan"]  # non-empty

    @pytest.mark.asyncio
    async def test_explain_no_adapters_returns_error(self):
        server.server_config = ServerConfig(security=SecurityConfig())
        raw = await server.explain("SELECT 1")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_explain_rejects_union_select(self, server_with_sqlite):
        # Vuln 2 fix: explain tool must apply SQLSanitizer like query tool does
        raw = await server.explain("SELECT * FROM users UNION SELECT * FROM users")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_explain_rejects_destructive_sql(self, server_with_sqlite):
        raw = await server.explain("DROP TABLE users")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_explain_rejects_sql_comment_injection(self, server_with_sqlite):
        raw = await server.explain("SELECT 1 -- injected comment")
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_explain_server_not_initialized_returns_error(self, adapter_with_data):
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = None
        raw = await server.explain("SELECT 1")
        result = json.loads(raw)
        assert "error" in result


class TestHealthTool:
    @pytest.mark.asyncio
    async def test_health_connected(self, server_with_sqlite):
        raw = await server.health()
        result = json.loads(raw)
        assert result["connected"] is True
        assert result["version"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_health_no_adapters_returns_error(self):
        server.server_config = ServerConfig(security=SecurityConfig())
        raw = await server.health()
        result = json.loads(raw)
        assert "error" in result


class TestListDatabasesTool:
    @pytest.mark.asyncio
    async def test_empty_when_no_adapters(self):
        raw = await server.list_databases()
        result = json.loads(raw)
        assert result["databases"] == []

    @pytest.mark.asyncio
    async def test_lists_connected_adapters(self, server_with_sqlite):
        raw = await server.list_databases()
        result = json.loads(raw)
        assert len(result["databases"]) == 1
        db = result["databases"][0]
        assert db["type"] == "sqlite"
        assert db["connected"] is True

    @pytest.mark.asyncio
    async def test_multiple_adapters_listed(self, adapter_with_data):
        config2 = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
        adapter2 = SQLiteAdapter(config2)
        await adapter2.connect()
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.adapters["sqlite:second"] = adapter2
        server.server_config = ServerConfig(security=SecurityConfig())
        try:
            raw = await server.list_databases()
            result = json.loads(raw)
            assert len(result["databases"]) == 2
        finally:
            await adapter2.disconnect()
