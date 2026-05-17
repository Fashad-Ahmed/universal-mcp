"""Base database adapter interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ..config import DatabaseConfig


@dataclass
class QueryResult:
    """Result from a database query."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    fields: List[Dict[str, str]] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass
class TableInfo:
    """Information about a database table."""

    name: str
    schema: Optional[str] = None
    columns: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SchemaInfo:
    """Database schema information."""

    tables: List[TableInfo] = field(default_factory=list)


@dataclass
class ExplainResult:
    """Query execution plan."""

    plan: str
    estimated_cost: Optional[float] = None
    estimated_rows: Optional[int] = None


@dataclass
class HealthStatus:
    """Database health check result."""

    connected: bool
    response_time_ms: float
    version: Optional[str] = None
    error: Optional[str] = None


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self.connected = False

    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection."""
        ...

    @abstractmethod
    async def query(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        """Execute a query and return results."""
        ...

    @abstractmethod
    async def get_schema(self, table_names: Optional[List[str]] = None) -> SchemaInfo:
        """Get database schema information."""
        ...

    @abstractmethod
    async def explain(self, sql: str, params: Optional[List[Any]] = None) -> ExplainResult:
        """Get query execution plan."""
        ...

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Check database health."""
        ...

    def is_connected(self) -> bool:
        return self.connected

    def get_type(self) -> str:
        return self.config.type

    def get_database(self) -> str:
        return self.config.database

    async def __aenter__(self) -> "DatabaseAdapter":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()
