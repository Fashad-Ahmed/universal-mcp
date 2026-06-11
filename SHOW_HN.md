# Show HN draft

## Title
Show HN: Universal DB MCP – security-first MCP server for Postgres/SQLite/MySQL/DuckDB

## Body
I built a Model Context Protocol (MCP) server that lets AI agents (Claude, etc.)
query databases without giving them a blank check.

Most DB MCP servers I found just hand the LLM raw SQL execution. This one assumes
the LLM is untrusted input: 8-layer SQL injection prevention (UNION/stacked-statement/
time-based/comment-bypass blocking), read-only by default, table allowlists, dry-run
mode (returns EXPLAIN instead of running), query complexity guards, and audit logging.

Zero infra needed for SQLite/DuckDB — `uvx universal-db-mcp` and you're querying a
local file. Postgres/MySQL via async drivers (asyncpg/aiomysql) with pool metrics
and concurrency limiting.

Demo GIF + full security writeup in the README.

GitHub: https://github.com/Fashad-Ahmed/universal-mcp
PyPI: https://pypi.org/project/universal-db-mcp/

Feedback on the security model especially welcome — happy to discuss tradeoffs
(e.g. why allowlist > blocklist, why read-only transactions aren't enough alone).
