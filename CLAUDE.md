# Universal Database MCP Server - Project Context

## Project Overview

This is a **production-grade Universal Database MCP Server** built with Python and FastMCP. It provides secure, multi-database connectivity (PostgreSQL, SQLite, MySQL) for AI agents like Claude Code.

**Critical Context**: This is enterprise infrastructure code. Security, reliability, and maintainability are paramount.

## Architecture Principles

1. **Security First**: All database access is read-only by default with SQL injection prevention
2. **Async Everything**: All database operations use async/await for performance
3. **Fail-Safe Defaults**: Conservative settings that can be explicitly relaxed
4. **Progressive Enhancement**: Start simple, add features incrementally
5. **Observable**: Comprehensive logging, health checks, and monitoring

## Tech Stack

- **Language**: Python 3.10+
- **MCP Framework**: FastMCP (official Python SDK)
- **Database Drivers**:
  - PostgreSQL: `asyncpg` (fastest async driver)
  - SQLite: `aiosqlite` (async wrapper)
  - MySQL: `aiomysql` (async wrapper)
- **Validation**: Pydantic v2 for runtime type safety
- **SQL Parsing**: `sqlparse` for query validation
- **Testing**: pytest with pytest-asyncio

## Code Standards

### Python Style
- Follow PEP 8 with 100-character line length
- Use type hints everywhere (`from typing import ...`)
- Async functions for all I/O operations
- Context managers for resource cleanup
- Descriptive variable names over comments

### Error Handling
- Never swallow exceptions silently
- Always provide actionable error messages
- Use custom exception classes for domain errors
- Log errors to stderr (MCP runs on stdio)

### Security Rules
- **NEVER** execute raw SQL without validation
- **ALWAYS** use parameterized queries
- **DEFAULT** to read-only mode
- **VALIDATE** all user inputs with Pydantic
- **SANITIZE** SQL identifiers before use
- **LIMIT** result set sizes to prevent DoS

### Testing Requirements
- Unit tests for all security functions
- Integration tests for each database adapter
- Mock external dependencies
- Test both success and failure paths
- Async tests use `@pytest.mark.asyncio`

## File Organization

```
src/universal_db_mcp/
├── __init__.py           # Package exports
├── server.py             # FastMCP server (main entry point)
├── config.py             # Configuration management
├── adapters/
│   ├── base.py           # Abstract base adapter
│   ├── postgresql.py     # PostgreSQL implementation
│   ├── sqlite.py         # SQLite implementation
│   └── mysql.py          # MySQL implementation
└── security/
    └── sanitizer.py      # SQL injection prevention

tests/
├── test_security.py      # Security validation tests
├── test_adapters.py      # Database adapter tests
└── conftest.py           # Pytest fixtures
```

## Common Patterns

### Adding a New Database Adapter
1. Subclass `DatabaseAdapter` in `adapters/base.py`
2. Implement all abstract methods
3. Add connection config to `config.py`
4. Register in `server.py` adapter factory
5. Add integration tests
6. Update documentation

### Adding a New MCP Tool
1. Define function in `server.py`
2. Add `@mcp.tool()` decorator
3. Use Pydantic for parameter validation
4. Return JSON string (FastMCP requirement)
5. Handle errors gracefully
6. Add docstring with parameter descriptions

### Security Validation Pattern
```python
# ALWAYS validate queries before execution
is_valid, errors = SQLSanitizer.validate_query(sql, allow_destructive)
if not is_valid:
    return json.dumps({"error": "Validation failed", "details": errors})

# Execute with try/except
try:
    result = await adapter.query(sql, params)
except Exception as e:
    return json.dumps({"error": str(e), "type": type(e).__name__})
```

## Environment Variables

All config comes from environment variables (12-factor app):
- `POSTGRES_URI` or individual `POSTGRES_HOST`, `POSTGRES_PORT`, etc.
- `SQLITE_PATH` for SQLite database file
- `MYSQL_URI` or individual MySQL settings
- `ALLOW_DESTRUCTIVE=false` to enable write operations
- `MAX_RESULT_ROWS=1000` to limit result sizes
- `ENABLE_LOGGING=true` for query logging

## Development Workflow

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Locally
```bash
# Set environment variables
export POSTGRES_URI=postgresql://localhost/testdb
export SQLITE_PATH=./test.db

# Run server
python -m universal_db_mcp.server
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/universal_db_mcp --cov-report=term-missing

# Run specific test file
pytest tests/test_security.py -v
```

### Pre-commit Checks
Before committing:
1. Format code: `black src/ tests/`
2. Lint: `ruff check src/ tests/`
3. Type check: `mypy src/`
4. Run tests: `pytest`

## Critical Security Notes

### SQL Injection Prevention
We use a **layered defense**:
1. **Query parsing** with sqlparse to detect structure
2. **Keyword blocking** for destructive operations in read-only mode
3. **Pattern matching** for common injection techniques
4. **Parameterized queries** enforced at execution time
5. **Type validation** on all parameters

### Read-Only Mode
- Enabled by default for all databases
- Blocks: DROP, DELETE, TRUNCATE, ALTER, CREATE, INSERT, UPDATE
- Uses database-level read-only transactions where supported
- Can be disabled per-database with `ALLOW_DESTRUCTIVE=true`

### Rate Limiting
- Configurable via `RATE_LIMIT_RPM` (requests per minute)
- Protects against accidental infinite loops
- Implemented at the MCP tool level

## Common Issues

### "Database not connected"
- Adapter failed to initialize
- Check connection string format
- Verify database is running and accessible
- Check firewall/network settings

### "Query validation failed"
- You're trying to run a destructive query in read-only mode
- Check query syntax with sqlparse
- Ensure query doesn't have multiple statements

### "Results truncated"
- Query returned more than MAX_RESULT_ROWS
- Increase limit or add WHERE clause to narrow results
- Consider pagination for large datasets

## MCP Integration

This server exposes 5 tools via MCP:
1. **query** - Execute SQL queries
2. **schema** - Get database schema info
3. **explain** - Get query execution plans
4. **health** - Check database connectivity
5. **list_databases** - Show configured databases

Claude Code automatically discovers these tools when the server is configured in `.claude/mcp-servers.json` or `~/.config/claude-code/mcp-servers.json`.

## Performance Considerations

- PostgreSQL: asyncpg is 3x faster than psycopg2
- SQLite: Single connection only (file locking)
- MySQL: Connection pooling with aiomysql
- Typical query: 10-100ms (database latency dominates)
- Python overhead: ~1-5ms (negligible)

## Deployment

### Local Development
Use `uvx universal-db-mcp` for zero-install execution.

### Production
1. Create dedicated read-only database user
2. Use connection pooling
3. Set conservative query timeouts
4. Enable audit logging
5. Monitor connection health
6. Use environment variables for secrets

## Future Enhancements

- [ ] MongoDB adapter for NoSQL support
- [ ] Query result caching with Redis
- [ ] Query builder for natural language to SQL
- [ ] Streaming results for large datasets
- [ ] GraphQL endpoint
- [ ] Rate limiting with token bucket
- [ ] Audit log export

## Documentation

- Full API docs: `docs/API.md`
- Security guide: `docs/SECURITY.md`
- Deployment guide: `docs/DEPLOYMENT.md`
- Contributing: `CONTRIBUTING.md`

## Key Decisions

**Why Python over TypeScript?**
- Better database driver ecosystem
- Simpler async/await syntax
- FastMCP has less boilerplate
- Dominant in data engineering

**Why FastMCP over raw MCP SDK?**
- 50% less code
- Official Python SDK
- Decorator-based API
- Built-in error handling

**Why asyncpg over psycopg2?**
- 3x faster for queries
- Native async support
- Better connection pooling
- Type-safe parameter binding

**Why multiple adapters vs single ORM?**
- Database-specific optimizations
- No ORM overhead
- Direct feature access (EXPLAIN, etc.)
- Clearer error messages

## Contact & Support

For issues, see `CONTRIBUTING.md` for how to report bugs or request features.

---

**Remember**: This is infrastructure code that AI agents will use to access production databases. Every line of code is a potential security or reliability risk. When in doubt, be more conservative, not less.
