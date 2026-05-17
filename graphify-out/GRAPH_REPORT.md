# Graph Report - .  (2026-05-17)

## Corpus Check
- Corpus is ~12,433 words - fits in a single context window. You may not need a graph.

## Summary
- 256 nodes · 434 edges · 26 communities (10 shown, 16 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 103 edges (avg confidence: 0.63)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_SQL Injection Prevention|SQL Injection Prevention]]
- [[_COMMUNITY_MCP Server Tools|MCP Server Tools]]
- [[_COMMUNITY_Database Adapter Interface|Database Adapter Interface]]
- [[_COMMUNITY_Server Lifecycle & Routing|Server Lifecycle & Routing]]
- [[_COMMUNITY_Configuration & Security Design|Configuration & Security Design]]
- [[_COMMUNITY_SQLite Adapter & Tests|SQLite Adapter & Tests]]
- [[_COMMUNITY_Adapter Integration Tests|Adapter Integration Tests]]
- [[_COMMUNITY_Query Result & PostgreSQL|Query Result & PostgreSQL]]
- [[_COMMUNITY_MySQL Adapter|MySQL Adapter]]
- [[_COMMUNITY_Explain  Query Plan|Explain / Query Plan]]
- [[_COMMUNITY_Health Check|Health Check]]
- [[_COMMUNITY_FastMCP Entry Point|FastMCP Entry Point]]
- [[_COMMUNITY_Package Init|Package Init]]
- [[_COMMUNITY_Query Validation Logic|Query Validation Logic]]
- [[_COMMUNITY_Keyword Extraction|Keyword Extraction]]
- [[_COMMUNITY_Identifier Sanitizer|Identifier Sanitizer]]
- [[_COMMUNITY_Read-Only Query Check|Read-Only Query Check]]
- [[_COMMUNITY_DSN Password Masking|DSN Password Masking]]
- [[_COMMUNITY_Connect Abstract Method|Connect Abstract Method]]
- [[_COMMUNITY_Disconnect Abstract Method|Disconnect Abstract Method]]
- [[_COMMUNITY_Execute Query Abstract|Execute Query Abstract]]
- [[_COMMUNITY_Schema Introspection Abstract|Schema Introspection Abstract]]
- [[_COMMUNITY_Explain Abstract Method|Explain Abstract Method]]
- [[_COMMUNITY_Health Check Abstract|Health Check Abstract]]

## God Nodes (most connected - your core abstractions)
1. `SQLiteAdapter` - 41 edges
2. `DatabaseConfig` - 36 edges
3. `PostgreSQLAdapter` - 30 edges
4. `MySQLAdapter` - 30 edges
5. `SecurityConfig` - 17 edges
6. `ServerConfig` - 16 edges
7. `DatabaseAdapter` - 15 edges
8. `TestHelperMethods` - 12 edges
9. `SQLSanitizer` - 12 edges
10. `TestInjectionPatternDetection` - 11 edges

## Surprising Connections (you probably didn't know these)
- `validate_query()` --conceptually_related_to--> `Read-Only by Default`  [INFERRED]
  src/universal_db_mcp/security/sanitizer.py → CLAUDE.md
- `base_security_config()` --calls--> `SecurityConfig`  [INFERRED]
  tests/conftest.py → src/universal_db_mcp/config.py
- `Security-First / Multi-Layer Defense` --rationale_for--> `SQLSanitizer`  [EXTRACTED]
  CLAUDE.md → src/universal_db_mcp/security/sanitizer.py
- `Adapter Pattern (database abstraction)` --rationale_for--> `DatabaseAdapter`  [EXTRACTED]
  PROJECT_SUMMARY.md → src/universal_db_mcp/adapters/base.py
- `Factory Pattern (adapter creation)` --rationale_for--> `_create_adapter`  [EXTRACTED]
  PROJECT_SUMMARY.md → src/universal_db_mcp/server.py

## Hyperedges (group relationships)
- **Query Validation Pipeline: validate_query gates adapter.query via server query tool** — server_query_tool, security_sanitizer_validate_query, adapters_base_databaseadapter [EXTRACTED 1.00]
- **Adapter Factory: _create_adapter produces PostgreSQL, SQLite, MySQL adapters from DatabaseConfig** — server_create_adapter, adapters_postgresql_postgresqladapter, adapters_sqlite_sqliteadapter, adapters_mysql_mysqladapter, config_databaseconfig [EXTRACTED 1.00]
- **Test Isolation: reset_server_state autouse fixture cleans up server globals for all MCP tool tests** — tests_conftest_reset_server_state, tests_test_mcp_tools_testquerytool, tests_test_mcp_tools_testschematool, tests_test_mcp_tools_testexplaintool [EXTRACTED 0.95]

## Communities (26 total, 16 thin omitted)

### Community 0 - "SQL Injection Prevention"
Cohesion: 0.05
Nodes (18): Parameterized Queries for Injection Safety, SQL security and injection prevention., DANGEROUS_PATTERNS, DESTRUCTIVE_KEYWORDS, _extract_first_keyword(), is_read_only_query(), mask_dsn(), SQL injection prevention and query validation. (+10 more)

### Community 1 - "MCP Server Tools"
Cohesion: 0.07
Nodes (28): BaseModel, Universal Database MCP Server (README), _error, explain (MCP tool), _get_adapter, health (MCP tool), list_databases (MCP tool), query (MCP tool) (+20 more)

### Community 2 - "Database Adapter Interface"
Cohesion: 0.08
Nodes (16): ABC, connect(), DatabaseAdapter, disconnect(), Base database adapter interface., Information about a database table., Database schema information., Abstract base class for database adapters. (+8 more)

### Community 3 - "Server Lifecycle & Routing"
Cohesion: 0.16
Nodes (19): _cleanup_adapters(), _create_adapter(), _error(), explain(), _get_adapter(), health(), _initialize_adapters(), lifespan() (+11 more)

### Community 4 - "Configuration & Security Design"
Cohesion: 0.11
Nodes (18): CLAUDE.md Project Context, Factory Pattern (adapter creation), Read-Only by Default, Security-First / Multi-Layer Defense, DatabaseConfig, load_config, SecurityConfig, ServerConfig (+10 more)

### Community 5 - "SQLite Adapter & Tests"
Cohesion: 0.16
Nodes (17): SQLite adapter using aiosqlite., SQLiteAdapter, pg_adapter(), test_disconnect_sets_flag(), test_file_db_connect(), test_health_disconnected(), test_in_memory_connect(), test_readonly_file_db() (+9 more)

### Community 7 - "Query Result & PostgreSQL"
Cohesion: 0.22
Nodes (5): QueryResult, Result from a database query., PostgreSQLAdapter, PostgreSQL adapter using asyncpg connection pooling., TestPostgreSQLAdapter

### Community 8 - "MySQL Adapter"
Cohesion: 0.2
Nodes (6): MySQLAdapter, MySQL adapter using aiomysql connection pooling., Connection Pooling, DatabaseAdapter, mysql_adapter(), TestMySQLAdapter

## Knowledge Gaps
- **57 isolated node(s):** `Tests for SQL injection prevention and sanitizer.`, `Shared pytest fixtures.`, `Isolate server globals between tests.`, `Integration tests for FastMCP server tools using SQLite in-memory.`, `Provide a connected in-memory SQLite adapter seeded with test data.` (+52 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SQLiteAdapter` connect `SQLite Adapter & Tests` to `MCP Server Tools`, `Database Adapter Interface`, `Server Lifecycle & Routing`, `Configuration & Security Design`, `Adapter Integration Tests`, `Query Result & PostgreSQL`, `MySQL Adapter`, `Explain / Query Plan`, `Health Check`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Why does `validate_query()` connect `SQL Injection Prevention` to `MCP Server Tools`, `Configuration & Security Design`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Why does `query (MCP tool)` connect `MCP Server Tools` to `SQL Injection Prevention`, `Configuration & Security Design`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `SQLiteAdapter` (e.g. with `TestQueryTool` and `TestSchemaTool`) actually correct?**
  _`SQLiteAdapter` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `DatabaseConfig` (e.g. with `TestQueryTool` and `TestSchemaTool`) actually correct?**
  _`DatabaseConfig` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `PostgreSQLAdapter` (e.g. with `TestSQLiteConnect` and `TestSQLiteQuery`) actually correct?**
  _`PostgreSQLAdapter` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MySQLAdapter` (e.g. with `TestSQLiteConnect` and `TestSQLiteQuery`) actually correct?**
  _`MySQLAdapter` has 11 INFERRED edges - model-reasoned connections that need verification._