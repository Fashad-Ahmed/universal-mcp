"""Database adapters for PostgreSQL, SQLite, and MySQL."""

from .base import DatabaseAdapter, QueryResult, SchemaInfo, TableInfo, ExplainResult, HealthStatus
from .postgresql import PostgreSQLAdapter
from .sqlite import SQLiteAdapter
from .mysql import MySQLAdapter

__all__ = [
    "DatabaseAdapter",
    "QueryResult",
    "SchemaInfo",
    "TableInfo",
    "ExplainResult",
    "HealthStatus",
    "PostgreSQLAdapter",
    "SQLiteAdapter",
    "MySQLAdapter",
]
