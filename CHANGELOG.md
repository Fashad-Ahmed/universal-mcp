# Changelog

## v1.1.1

### Fixed
- Resolved bandit B608 false positives in PostgreSQL/MySQL/SQLite/DuckDB schema
  introspection queries (CI security scan now passes cleanly).

## v1.1.0

### Added
- **Dry-run mode** (`DRYRUN=true`): `query` returns the execution plan via `EXPLAIN` instead of running the SQL.
- **Table allowlist enforcement** (`WHITELISTED_TABLES`): queries referencing tables outside the allowlist are rejected before execution.
- **Schema drift detection**: new `snapshot_schema` and `schema_diff` tools to capture and compare schema state over time.
- **Query history**: new `query_history` tool exposing the last 100 executed queries (sql, database, execution time, row count, timestamp).
- **Structured audit logging**: query events are logged to stderr as JSON.
- **Concurrency limiting**: queries are bounded by a semaphore (max 10 concurrent) to protect database connections.
- **Connection pool metrics**: `health` now reports `pool_size` and `pool_idle` for PostgreSQL.
- **`--check` CLI flag**: validates configuration and tests connectivity to all configured databases. `--version` prints the installed version.
- **Query complexity guard**: queries with excessive JOINs (`MAX_JOINS`) or unbounded `SELECT *` trigger non-blocking `complexity_warnings`.
- CI workflow: test matrix across Python 3.10/3.11/3.12 on Ubuntu/macOS, plus `bandit` security scan.
- Publish workflow: automated PyPI release on `v*` tags.

### Changed
- `pyproject.toml`: added PyPI classifiers, bumped version to 1.1.0.
- `.env.example`: documented new environment variables (`DRYRUN`, `MAX_JOINS`, `WARN_SELECT_STAR_NO_LIMIT`, `WHITELISTED_TABLES`).

## v1.0.0

Initial release: PostgreSQL, SQLite, MySQL, and DuckDB adapters with read-only-by-default security model.
