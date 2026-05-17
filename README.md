# Universal Database MCP Server

**Production-grade MCP server for secure database access from AI agents.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-green.svg)](https://github.com/jlowin/fastmcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 What Is This?

A secure, multi-database MCP server that lets AI agents (like Claude Code) query your databases safely. Built with enterprise-grade security: read-only by default, SQL injection prevention, and comprehensive audit logging.

**Supports**: PostgreSQL, SQLite, MySQL

## ⚡ Quick Start

```bash
# Zero-install execution
POSTGRES_URI=postgresql://localhost/mydb uvx universal-db-mcp

# Or install locally
pip install -e .
universal-db-mcp
```

## 🔒 Security First

- ✅ **Read-only by default** - Destructive operations blocked
- ✅ **SQL injection prevention** - Multi-layer validation
- ✅ **Parameterized queries** - No string concatenation
- ✅ **Minimal permissions** - Dedicated database users
- ✅ **Audit logging** - All queries tracked
- ✅ **Rate limiting** - DoS protection

## 📋 Features

- **Multi-Database**: Connect PostgreSQL, SQLite, and MySQL simultaneously
- **Schema Introspection**: Automatic table and column discovery
- **Query Planning**: EXPLAIN support for optimization
- **Health Checks**: Connection monitoring
- **FastMCP**: Clean decorator-based API
- **Async**: Non-blocking I/O for performance
- **Type Safe**: Pydantic validation everywhere

## 🚀 Installation

### Option 1: Zero-Install (Recommended)
```bash
uvx universal-db-mcp
```

### Option 2: Local Install
```bash
git clone <repo-url>
cd universal-db-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Option 3: Docker
```bash
docker build -t universal-db-mcp .
docker run -e POSTGRES_URI=... universal-db-mcp
```

## ⚙️ Configuration

Create `.env`:

```bash
# PostgreSQL
POSTGRES_URI=postgresql://readonly:password@localhost:5432/mydb
POSTGRES_READONLY=true

# SQLite
SQLITE_PATH=/path/to/database.db
SQLITE_READONLY=true

# MySQL
MYSQL_URI=mysql://readonly:password@localhost:3306/mydb
MYSQL_READONLY=true

# Security
ALLOW_DESTRUCTIVE=false
MAX_RESULT_ROWS=1000
ENABLE_LOGGING=true
QUERY_TIMEOUT=30
```

## 🔧 Claude Code Setup

Add to `~/.config/claude-code/mcp-servers.json`:

```json
{
  "mcpServers": {
    "database": {
      "command": "uvx",
      "args": ["universal-db-mcp"],
      "env": {
        "POSTGRES_URI": "postgresql://readonly:password@localhost/mydb",
        "ALLOW_DESTRUCTIVE": "false"
      }
    }
  }
}
```

## 📖 Usage

After configuration, use Claude Code naturally:

```
You: "Show me the top 10 users by signup date"
Claude: [uses query tool]

You: "What's the schema of the orders table?"
Claude: [uses schema tool]

You: "Explain this query: SELECT * FROM large_table WHERE date > NOW()"
Claude: [uses explain tool]
```

## 🛡️ Security Best Practices

### 1. Create Dedicated Database Users

**PostgreSQL**:
```sql
CREATE USER claude_readonly WITH PASSWORD 'strong_password_here';
GRANT CONNECT ON DATABASE mydb TO claude_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO claude_readonly;
```

**MySQL**:
```sql
CREATE USER 'claude_readonly'@'localhost' IDENTIFIED BY 'strong_password_here';
GRANT SELECT ON mydb.* TO 'claude_readonly'@'localhost';
```

### 2. Never Commit Credentials

Add to `.gitignore`:
```
.env
*.db
.env.*
```

### 3. Enable SSL for Remote Connections

```bash
POSTGRES_SSL=true
MYSQL_SSL=true
```

### 4. Review Audit Logs Regularly

```bash
# Logs go to stderr when running
tail -f ~/.claude/logs/universal-db-mcp.log
```

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/universal_db_mcp --cov-report=term-missing

# Security tests only
pytest tests/test_security.py -v
```

## 📁 Project Structure

```
universal-db-mcp/
├── .claude/
│   └── skills/              # Claude Code skills
│       ├── db-mcp-deploy/   # Deployment guide
│       ├── db-security-audit/ # Security audit
│       └── mcp-testing/     # Testing workflow
├── src/
│   └── universal_db_mcp/
│       ├── server.py        # FastMCP server
│       ├── config.py        # Configuration
│       ├── adapters/        # Database adapters
│       └── security/        # SQL sanitization
├── tests/                   # Test suite
├── docs/                    # Documentation
├── CLAUDE.md                # Project context
└── README.md               # This file
```

## 🔧 Development

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Code Style
```bash
black src/ tests/
ruff check src/ tests/
mypy src/
```

### Pre-commit Hooks
```bash
pre-commit install
```

## 📚 Documentation

- [API Reference](docs/API.md)
- [Security Guide](docs/SECURITY.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Contributing](CONTRIBUTING.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Inspired by the MCP community
- Security patterns from OWASP

## 📞 Support

- Issues: [GitHub Issues](https://github.com/yourusername/universal-db-mcp/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/universal-db-mcp/discussions)

---

**⚠️ Security Notice**: This tool provides AI agents with database access. Always use read-only credentials, enable audit logging, and review security settings before production deployment.
