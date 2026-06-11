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


class TestDryRunMode:
    @pytest.mark.asyncio
    async def test_dry_run_returns_plan_without_executing(self, adapter_with_data):
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = ServerConfig(
            security=SecurityConfig(allow_destructive=True, enable_logging=False, dry_run=True)
        )
        raw = await server.query("INSERT INTO users VALUES (3, 'Carol', 'carol@example.com')")
        result = json.loads(raw)
        assert result["dry_run"] is True
        assert "plan" in result

        check = await adapter_with_data.query("SELECT COUNT(*) AS c FROM users")
        assert check.rows[0]["c"] == 2


class TestTableAllowlist:
    @pytest.mark.asyncio
    async def test_allowed_table_passes(self, adapter_with_data):
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = ServerConfig(
            security=SecurityConfig(
                allow_destructive=True,
                enable_logging=False,
                whitelisted_tables=["users"],
            )
        )
        raw = await server.query("SELECT * FROM users")
        result = json.loads(raw)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_disallowed_table_blocked(self, adapter_with_data):
        server.adapters["sqlite::memory:"] = adapter_with_data
        server.server_config = ServerConfig(
            security=SecurityConfig(
                allow_destructive=True,
                enable_logging=False,
                whitelisted_tables=["orders"],
            )
        )
        raw = await server.query("SELECT * FROM users")
        result = json.loads(raw)
        assert "error" in result
        assert "users" in result["details"]


class TestQueryHistory:
    @pytest.mark.asyncio
    async def test_history_records_query(self, server_with_sqlite):
        server._query_history.clear()
        await server.query("SELECT * FROM users")
        raw = await server.query_history(limit=10)
        result = json.loads(raw)
        assert len(result["history"]) == 1
        assert result["history"][0]["sql"] == "SELECT * FROM users"

    @pytest.mark.asyncio
    async def test_history_most_recent_first(self, server_with_sqlite):
        server._query_history.clear()
        await server.query("SELECT 1")
        await server.query("SELECT 2")
        raw = await server.query_history(limit=10)
        result = json.loads(raw)
        assert result["history"][0]["sql"] == "SELECT 2"
        assert result["history"][1]["sql"] == "SELECT 1"


class TestSchemaDrift:
    @pytest.mark.asyncio
    async def test_diff_without_snapshot_errors(self, server_with_sqlite):
        raw = await server.schema_diff()
        result = json.loads(raw)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_snapshot_then_no_diff(self, server_with_sqlite):
        raw = await server.snapshot_schema()
        result = json.loads(raw)
        assert result["tables_snapshotted"] >= 1

        raw = await server.schema_diff()
        result = json.loads(raw)
        assert result["added_tables"] == []
        assert result["dropped_tables"] == []
        assert result["column_changes"] == {}

    @pytest.mark.asyncio
    async def test_diff_detects_new_table(self, server_with_sqlite, adapter_with_data):
        await server.snapshot_schema()
        await adapter_with_data.query("CREATE TABLE orders (id INTEGER PRIMARY KEY)")

        raw = await server.schema_diff()
        result = json.loads(raw)
        assert "orders" in result["added_tables"]

    @pytest.mark.asyncio
    async def test_diff_detects_new_column(self, server_with_sqlite, adapter_with_data):
        await server.snapshot_schema()
        await adapter_with_data.query("ALTER TABLE users ADD COLUMN age INTEGER")

        raw = await server.schema_diff()
        result = json.loads(raw)
        assert "age" in result["column_changes"]["users"]["added_columns"]


class TestComplexityWarnings:
    @pytest.mark.asyncio
    async def test_select_star_no_limit_warns(self, server_with_sqlite):
        raw = await server.query("SELECT * FROM users")
        result = json.loads(raw)
        assert "complexity_warnings" in result


class TestRunCheck:
    @pytest.mark.asyncio
    async def test_run_check_with_no_databases(self, monkeypatch):
        from src.universal_db_mcp.config import ServerConfig as SC

        monkeypatch.setattr(
            "src.universal_db_mcp.server.load_config", lambda: SC(databases=[])
        )
        exit_code = await server._run_check()
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_run_check_with_sqlite(self, monkeypatch, tmp_db):
        from src.universal_db_mcp.config import ServerConfig as SC

        config = SC(databases=[DatabaseConfig(type="sqlite", database=tmp_db, read_only=False)])
        monkeypatch.setattr("src.universal_db_mcp.server.load_config", lambda: config)
        exit_code = await server._run_check()
        assert exit_code == 0
