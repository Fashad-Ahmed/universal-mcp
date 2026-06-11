# Security Policy

## Reporting a Vulnerability

Found a bypass of the SQL injection sanitizer, the DuckDB filesystem blocklist,
or any other security control? Please report it privately to
**fashad.ahmed20@gmail.com** before opening a public issue.

Include:
- A proof-of-concept query or config that triggers the issue
- Which security layer it bypasses (see [docs/SECURITY.md](docs/SECURITY.md))
- The affected adapter (PostgreSQL, SQLite, MySQL, DuckDB)

We aim to acknowledge reports within 48 hours.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | ✅ |
| 1.0.x   | ✅ |
| < 1.0   | ❌ |

## Full Threat Model

See [docs/SECURITY.md](docs/SECURITY.md) for the complete 8-layer security model
and threat model summary.
