"""Configuration management for Universal Database MCP Server."""

import os
from typing import Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfig(BaseModel):
    """Configuration for a single database connection."""

    type: str = Field(..., description="Database type: postgresql, sqlite, mysql, duckdb")
    host: Optional[str] = None
    port: Optional[int] = None
    database: str = Field(..., description="Database name or file path")
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None
    ssl: bool = False
    read_only: bool = True
    max_connections: int = 10
    query_timeout: int = 30


class SecurityConfig(BaseModel):
    """Security configuration."""

    allow_destructive: bool = False
    max_result_rows: int = 1000
    enable_logging: bool = True
    whitelisted_tables: Optional[List[str]] = None
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10


class ServerConfig(BaseModel):
    """Complete server configuration."""

    name: str = "universal-db-mcp"
    version: str = "1.0.0"
    databases: List[DatabaseConfig] = Field(default_factory=list)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


def load_config() -> ServerConfig:
    """Load configuration from environment variables."""
    config = ServerConfig(
        name=os.getenv("MCP_SERVER_NAME", "universal-db-mcp"),
        security=SecurityConfig(
            allow_destructive=os.getenv("ALLOW_DESTRUCTIVE", "false").lower() == "true",
            max_result_rows=int(os.getenv("MAX_RESULT_ROWS", "1000")),
            enable_logging=os.getenv("ENABLE_LOGGING", "true").lower() == "true",
            whitelisted_tables=(
                os.getenv("WHITELISTED_TABLES", "").split(",")
                if os.getenv("WHITELISTED_TABLES")
                else None
            ),
            rate_limit_rpm=int(os.getenv("RATE_LIMIT_RPM", "60")),
            rate_limit_burst=int(os.getenv("RATE_LIMIT_BURST", "10")),
        ),
    )

    if os.getenv("POSTGRES_URI") or os.getenv("POSTGRES_HOST"):
        config.databases.append(
            DatabaseConfig(
                type="postgresql",
                connection_string=os.getenv("POSTGRES_URI"),
                host=os.getenv("POSTGRES_HOST"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "postgres"),
                username=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                ssl=os.getenv("POSTGRES_SSL", "false").lower() == "true",
                read_only=os.getenv("POSTGRES_READONLY", "true").lower() == "true",
                max_connections=int(os.getenv("POSTGRES_MAX_CONN", "10")),
                query_timeout=int(os.getenv("QUERY_TIMEOUT", "30")),
            )
        )

    if os.getenv("SQLITE_PATH"):
        config.databases.append(
            DatabaseConfig(
                type="sqlite",
                database=os.getenv("SQLITE_PATH", ""),
                read_only=os.getenv("SQLITE_READONLY", "true").lower() == "true",
                query_timeout=int(os.getenv("QUERY_TIMEOUT", "30")),
            )
        )

    if os.getenv("MYSQL_URI") or os.getenv("MYSQL_HOST"):
        config.databases.append(
            DatabaseConfig(
                type="mysql",
                connection_string=os.getenv("MYSQL_URI"),
                host=os.getenv("MYSQL_HOST"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                database=os.getenv("MYSQL_DB", "mysql"),
                username=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                ssl=os.getenv("MYSQL_SSL", "false").lower() == "true",
                read_only=os.getenv("MYSQL_READONLY", "true").lower() == "true",
                max_connections=int(os.getenv("MYSQL_MAX_CONN", "10")),
                query_timeout=int(os.getenv("QUERY_TIMEOUT", "30")),
            )
        )

    if os.getenv("DUCKDB_PATH"):
        config.databases.append(
            DatabaseConfig(
                type="duckdb",
                database=os.getenv("DUCKDB_PATH", ":memory:"),
                read_only=os.getenv("DUCKDB_READONLY", "true").lower() == "true",
                query_timeout=int(os.getenv("QUERY_TIMEOUT", "30")),
            )
        )

    return config
