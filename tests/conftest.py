"""Shared pytest fixtures."""

import pytest
import pytest_asyncio

from src.universal_db_mcp.config import DatabaseConfig, SecurityConfig, ServerConfig
from src.universal_db_mcp.adapters.sqlite import SQLiteAdapter
import src.universal_db_mcp.server as server


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest_asyncio.fixture
async def memory_adapter():
    config = DatabaseConfig(type="sqlite", database=":memory:", read_only=False)
    adapter = SQLiteAdapter(config)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


@pytest_asyncio.fixture
async def memory_adapter_with_data(memory_adapter):
    await memory_adapter.query(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE)"
    )
    await memory_adapter.query(
        "INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')"
    )
    await memory_adapter.query(
        "INSERT INTO users VALUES (2, 'Bob', 'bob@example.com')"
    )
    return memory_adapter


@pytest.fixture
def base_security_config():
    return SecurityConfig(allow_destructive=True, max_result_rows=1000, enable_logging=False)


@pytest_asyncio.fixture(autouse=True)
async def reset_server_state():
    """Isolate server globals between tests."""
    original_adapters = dict(server.adapters)
    original_config = server.server_config
    server.adapters.clear()
    server.server_config = None
    yield
    await server._cleanup_adapters()
    server.adapters.clear()
    server.adapters.update(original_adapters)
    server.server_config = original_config
