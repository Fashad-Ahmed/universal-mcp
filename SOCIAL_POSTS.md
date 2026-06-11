# Social media drafts

## Twitter / X

🔒 Built an MCP server so AI agents can query your databases without YOLO-ing raw SQL.

universal-db-mcp: Postgres, SQLite, MySQL, DuckDB
- 8-layer SQL injection prevention
- read-only by default
- dry-run mode (EXPLAIN before execute)
- table allowlists

Zero infra: `uvx universal-db-mcp` 🚀

https://github.com/Fashad-Ahmed/universal-mcp

#MCP #ClaudeAI #opensource

---

## LinkedIn

Most "AI agent talks to your database" demos hand the LLM raw SQL execution and
hope for the best. That's a production incident waiting to happen.

I built Universal DB MCP — an open-source Model Context Protocol server that
treats LLM-generated SQL as untrusted input:

→ 8-layer SQL injection prevention (UNION attacks, stacked statements,
  time-based injection, comment bypasses)
→ Read-only by default, with explicit opt-in for writes
→ Table allowlists — restrict which tables an agent can even see
→ Dry-run mode — agent gets the EXPLAIN plan before anything executes
→ Audit logging + query history for every call

Supports PostgreSQL, MySQL, SQLite, and DuckDB. Zero infrastructure for
SQLite/DuckDB — one command (`uvx universal-db-mcp`) and Claude can query a
local file.

If you're building or evaluating AI agents with database access, I'd love
feedback on the security model.

GitHub: https://github.com/Fashad-Ahmed/universal-mcp
PyPI: https://pypi.org/project/universal-db-mcp/

#AI #MCP #OpenSource #DatabaseSecurity #ClaudeAI
