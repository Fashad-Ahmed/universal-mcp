"""DuckDB adapter integration tests. Uses in-memory database — zero external deps."""

import pytest
import pytest_asyncio

from src.universal_db_mcp.config import DatabaseConfig
from src.universal_db_mcp.adapters.duckdb import DuckDBAdapter


@pytest_asyncio.fixture
async def duck():
    """In-memory DuckDB adapter with seed data."""
    config = DatabaseConfig(type="duckdb", database=":memory:", read_only=False)
    adapter = DuckDBAdapter(config)
    await adapter.connect()
    await adapter.query("CREATE TABLE products (id INTEGER, name VARCHAR, price DOUBLE)")
    await adapter.query("INSERT INTO products VALUES (1, 'Widget', 9.99)")
    await adapter.query("INSERT INTO products VALUES (2, 'Gadget', 24.99)")
    yield adapter
    await adapter.disconnect()


class TestDuckDBConnect:
    @pytest.mark.asyncio
    async def test_in_memory_connect(self):
        config = DatabaseConfig(type="duckdb", database=":memory:", read_only=False)
        async with DuckDBAdapter(config) as adapter:
            assert adapter.connected

    @pytest.mark.asyncio
    async def test_disconnect_clears_flag(self):
        config = DatabaseConfig(type="duckdb", database=":memory:", read_only=False)
        adapter = DuckDBAdapter(config)
        await adapter.connect()
        assert adapter.connected
        await adapter.disconnect()
        assert not adapter.connected

    @pytest.mark.asyncio
    async def test_file_db_connect(self, tmp_path):
        db_file = str(tmp_path / "test.duckdb")
        config = DatabaseConfig(type="duckdb", database=db_file, read_only=False)
        async with DuckDBAdapter(config) as adapter:
            assert adapter.connected

    @pytest.mark.asyncio
    async def test_readonly_file_db(self, tmp_path):
        db_file = str(tmp_path / "test.duckdb")
        config_rw = DatabaseConfig(type="duckdb", database=db_file, read_only=False)
        async with DuckDBAdapter(config_rw) as adapter:
            await adapter.query("CREATE TABLE t (x INT)")

        config_ro = DatabaseConfig(type="duckdb", database=db_file, read_only=True)
        async with DuckDBAdapter(config_ro) as adapter:
            assert adapter.connected


class TestDuckDBQuery:
    @pytest.mark.asyncio
    async def test_select_one(self, duck):
        result = await duck.query("SELECT 42 AS val")
        assert result.rows[0]["val"] == 42
        assert result.row_count == 1

    @pytest.mark.asyncio
    async def test_insert_and_select(self, duck):
        result = await duck.query("SELECT * FROM products ORDER BY id")
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "Widget"

    @pytest.mark.asyncio
    async def test_parameterized_query(self, duck):
        result = await duck.query("SELECT * FROM products WHERE id = ?", [1])
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "Widget"

    @pytest.mark.asyncio
    async def test_fields_populated(self, duck):
        result = await duck.query("SELECT id, name FROM products LIMIT 1")
        field_names = [f["name"] for f in result.fields]
        assert "id" in field_names
        assert "name" in field_names

    @pytest.mark.asyncio
    async def test_execution_time_positive(self, duck):
        result = await duck.query("SELECT 1")
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_result(self, duck):
        result = await duck.query("SELECT * FROM products WHERE id = ?", [999])
        assert result.rows == []
        assert result.row_count == 0

    @pytest.mark.asyncio
    async def test_analytics_query(self, duck):
        result = await duck.query("SELECT COUNT(*) AS total, AVG(price) AS avg_price FROM products")
        assert result.rows[0]["total"] == 2
        assert result.rows[0]["avg_price"] == pytest.approx(17.49, rel=0.01)

    @pytest.mark.asyncio
    async def test_not_connected_raises(self):
        config = DatabaseConfig(type="duckdb", database=":memory:", read_only=False)
        adapter = DuckDBAdapter(config)
        with pytest.raises(RuntimeError, match="not connected"):
            await adapter.query("SELECT 1")


class TestDuckDBSchema:
    @pytest.mark.asyncio
    async def test_get_schema_lists_tables(self, duck):
        info = await duck.get_schema()
        names = [t.name for t in info.tables]
        assert "products" in names

    @pytest.mark.asyncio
    async def test_get_schema_columns(self, duck):
        info = await duck.get_schema(["products"])
        products = next(t for t in info.tables if t.name == "products")
        col_names = [c["name"] for c in products.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "price" in col_names

    @pytest.mark.asyncio
    async def test_get_schema_filter(self, duck):
        await duck.query("CREATE TABLE orders (id INTEGER, amount DOUBLE)")
        info = await duck.get_schema(["products"])
        assert len(info.tables) == 1
        assert info.tables[0].name == "products"

    @pytest.mark.asyncio
    async def test_get_schema_empty_db(self):
        config = DatabaseConfig(type="duckdb", database=":memory:", read_only=False)
        async with DuckDBAdapter(config) as adapter:
            info = await adapter.get_schema()
            assert info.tables == []


class TestDuckDBExplain:
    @pytest.mark.asyncio
    async def test_explain_returns_plan(self, duck):
        result = await duck.explain("SELECT * FROM products WHERE id = ?", [1])
        assert isinstance(result.plan, str)
        assert len(result.plan) > 0


class TestDuckDBHealth:
    @pytest.mark.asyncio
    async def test_health_connected(self, duck):
        status = await duck.health()
        assert status.connected
        assert status.version is not None
        assert "DuckDB" in status.version
        assert status.error is None

    @pytest.mark.asyncio
    async def test_health_not_initialized(self):
        config = DatabaseConfig(type="duckdb", database=":memory:", read_only=False)
        adapter = DuckDBAdapter(config)
        status = await adapter.health()
        assert not status.connected
        assert status.error is not None
