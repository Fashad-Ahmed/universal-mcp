# Security Architecture

This document details the multi-layer SQL injection prevention and security model
in the Universal Database MCP Server.

---

## Why AI Agents Need Stronger Security

When an LLM generates SQL, the threat model is different from traditional web apps:

- **No human review** — queries execute immediately without a developer checking them
- **Prompt injection** — a malicious document in the database could inject SQL into the LLM's context
- **Hallucinations** — the model may generate structurally valid but semantically dangerous SQL
- **Overly helpful** — the model may comply with `DROP TABLE` if the user accidentally asks for it

Standard ORM protections are insufficient. We need defense-in-depth.

---

## Layer 1: Read-Only by Default

Every database connection defaults to `read_only=True`. This is enforced at the
**driver level**, not just the application level:

| Database   | Enforcement mechanism                                      |
|------------|------------------------------------------------------------|
| PostgreSQL | `init` callback sets `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` on every pooled connection |
| SQLite     | `file:path?mode=ro` URI — OS-level read-only file open     |
| MySQL      | Transaction-level read-only flag per connection             |
| DuckDB     | `duckdb.connect(read_only=True)` — engine-level enforcement |

Even if an attacker bypasses Layer 2 and 3, the database driver rejects writes.

To enable writes: `ALLOW_DESTRUCTIVE=true` (explicit opt-in, per-database).

---

## Layer 2: Keyword Blocking (SQLSanitizer)

Before any query reaches the database, `SQLSanitizer.validate_query()` parses it
with `sqlparse` and rejects queries whose first keyword is in the destructive set:

```
DROP, DELETE, TRUNCATE, ALTER, CREATE, INSERT, UPDATE, GRANT, REVOKE, EXEC, EXECUTE
```

This runs even when `allow_destructive=True` is not set — providing a clear
error message to the AI agent instead of a cryptic database error.

---

## Layer 3: Injection Pattern Detection

Regex patterns catch common injection techniques regardless of destructive mode:

| Pattern                  | Blocks                                      |
|--------------------------|---------------------------------------------|
| `; DROP/DELETE/TRUNCATE` | Stacked statement attacks                   |
| `UNION SELECT`           | UNION-based data exfiltration               |
| `--`                     | SQL comment-based bypass                    |
| `/* ... */`              | Block comment bypass                        |
| `xp_`                    | MSSQL extended stored procedures            |
| `EXEC(` / `EXECUTE(`     | Dynamic SQL execution                       |
| `SLEEP(`                 | MySQL time-based blind injection            |
| `WAITFOR DELAY`          | MSSQL time-based blind injection            |
| `BENCHMARK(`             | MySQL CPU-based blind injection             |

These patterns apply to **all queries**, including `SELECT` statements, because
injection often piggybacks on read-only queries via UNION or stacked statements.

---

## Layer 4: Multiple Statement Rejection

`sqlparse` detects semicolons that separate multiple SQL statements. Any query
with more than one statement is rejected with a clear error:

```
Multiple SQL statements not allowed
```

This prevents attacks like:
```sql
SELECT * FROM users; DROP TABLE sessions; --
```

---

## Layer 5: Parameterized Query Enforcement

The MCP `query` tool validates parameter types before execution:

```python
# Only these types allowed as parameters
if not isinstance(p, (str, int, float, bool, type(None))):
    return _error("Invalid parameter type", [...])
```

Dict/list parameters are rejected. Queries that need dynamic values **must** use
`?` or `$N` placeholders — never string formatting.

---

## Layer 6: Result Size Limits

Every query result is capped at `MAX_RESULT_ROWS` (default: 1000). This prevents:

- Accidental full-table dumps
- Memory exhaustion from `SELECT *` on large tables
- Slow responses that degrade the agent's context window

Truncation is surfaced as a `warning` field in the response so the agent can
add a `LIMIT` clause or paginate.

---

## Layer 7: Identifier Sanitization

When building dynamic SQL internally (e.g., schema introspection), table and
column names pass through `SQLSanitizer.sanitize_identifier()`:

```python
re.sub(r"[^a-zA-Z0-9_]", "", identifier)
```

This strips SQL metacharacters from identifiers before they appear in any
internally-generated query.

---

## Threat Model Summary

| Threat                        | Mitigated by                           |
|-------------------------------|----------------------------------------|
| Prompt injection → DROP TABLE | Layers 1, 2                            |
| UNION-based exfiltration      | Layer 3                                |
| Stacked statement attack      | Layers 3, 4                            |
| Time-based blind injection    | Layer 3                                |
| Parameter smuggling           | Layer 5                                |
| Full-table data exfil         | Layer 6                                |
| Dynamic SQL identifier attack | Layer 7                                |
| Compromised LLM output        | All layers (defense-in-depth)          |

---

## What We Don't Protect Against

Be explicit about scope:

- **Legitimate destructive queries** — if `ALLOW_DESTRUCTIVE=true`, writes are
  permitted. Use a read-only database user for additional safety.
- **Privilege escalation** — we trust the database user's permissions. Always use
  the least-privileged DB account.
- **Data-level authorization** — we don't restrict which rows the agent can see.
  Use row-level security in PostgreSQL if needed.
- **Semantic attacks** — a crafted query that is syntactically safe but returns
  sensitive data (e.g., `SELECT password FROM users`) is allowed if the user has
  read permission. Restrict this at the DB user level.

---

## Creating Secure Database Users

### PostgreSQL — read-only

```sql
CREATE USER mcp_agent WITH PASSWORD 'strong_random_password';
GRANT CONNECT ON DATABASE mydb TO mcp_agent;
GRANT USAGE ON SCHEMA public TO mcp_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_agent;
```

### MySQL — read-only

```sql
CREATE USER 'mcp_agent'@'localhost' IDENTIFIED BY 'strong_random_password';
GRANT SELECT ON mydb.* TO 'mcp_agent'@'localhost';
FLUSH PRIVILEGES;
```

### SQLite — read-only

Set `SQLITE_READONLY=true` — the driver opens the file with `O_RDONLY`.
No separate user model needed.

### DuckDB — read-only

Set `DUCKDB_READONLY=true` — `duckdb.connect(read_only=True)` enforces this
at the engine level; any write attempt raises an exception before reaching SQL execution.

---

## Reporting Security Issues

Found a bypass? Please report privately to fashad.ahmed20@gmail.com before
opening a public issue. Include a proof-of-concept query that bypasses one of
the layers documented above.
