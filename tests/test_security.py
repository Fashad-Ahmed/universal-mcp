"""Tests for SQL injection prevention and sanitizer."""

import pytest
from src.universal_db_mcp.security.sanitizer import SQLSanitizer


class TestValidateQuery:
    def test_empty_query_rejected(self):
        valid, errors = SQLSanitizer.validate_query("")
        assert not valid
        assert any("empty" in e.lower() for e in errors)

    def test_whitespace_query_rejected(self):
        valid, errors = SQLSanitizer.validate_query("   ")
        assert not valid

    def test_select_allowed_readonly(self):
        valid, errors = SQLSanitizer.validate_query("SELECT * FROM users", allow_destructive=False)
        assert valid, errors

    def test_select_with_params_allowed(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT id, name FROM users WHERE id = %s", allow_destructive=False
        )
        assert valid, errors

    def test_explain_allowed(self):
        valid, errors = SQLSanitizer.validate_query(
            "EXPLAIN SELECT * FROM users", allow_destructive=False
        )
        assert valid, errors


class TestDestructiveKeywordBlocking:
    def test_drop_blocked_readonly(self):
        valid, errors = SQLSanitizer.validate_query("DROP TABLE users", allow_destructive=False)
        assert not valid
        assert any("DROP" in e for e in errors)

    def test_delete_blocked_readonly(self):
        valid, errors = SQLSanitizer.validate_query("DELETE FROM users", allow_destructive=False)
        assert not valid
        assert any("DELETE" in e for e in errors)

    def test_truncate_blocked_readonly(self):
        valid, errors = SQLSanitizer.validate_query("TRUNCATE TABLE users", allow_destructive=False)
        assert not valid

    def test_insert_blocked_readonly(self):
        valid, errors = SQLSanitizer.validate_query(
            "INSERT INTO users VALUES (1, 'x')", allow_destructive=False
        )
        assert not valid

    def test_update_blocked_readonly(self):
        valid, errors = SQLSanitizer.validate_query(
            "UPDATE users SET name='x'", allow_destructive=False
        )
        assert not valid

    def test_drop_allowed_when_destructive_enabled(self):
        valid, errors = SQLSanitizer.validate_query("DROP TABLE users", allow_destructive=True)
        assert valid, errors

    def test_insert_allowed_when_destructive_enabled(self):
        valid, errors = SQLSanitizer.validate_query(
            "INSERT INTO users VALUES (1, 'x')", allow_destructive=True
        )
        assert valid, errors


class TestInjectionPatternDetection:
    def test_stacked_drop_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT 1; DROP TABLE users", allow_destructive=True
        )
        assert not valid

    def test_union_select_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT * FROM users UNION SELECT * FROM passwords",
            allow_destructive=False,
        )
        assert not valid
        assert any("union" in e.lower() or "UNION" in e for e in errors)

    def test_sql_comment_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT * FROM users WHERE id=1 -- ignore rest",
            allow_destructive=False,
        )
        assert not valid

    def test_block_comment_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT /* bypass */ * FROM users",
            allow_destructive=False,
        )
        assert not valid

    def test_xp_cmdshell_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "EXEC xp_cmdshell('whoami')", allow_destructive=True
        )
        assert not valid

    def test_sleep_injection_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT * FROM users WHERE id=1 AND sleep(5)",
            allow_destructive=False,
        )
        assert not valid

    def test_waitfor_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "WAITFOR DELAY '0:0:5'", allow_destructive=True
        )
        assert not valid

    def test_benchmark_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT benchmark(1000000, md5('test'))", allow_destructive=False
        )
        assert not valid


class TestMultipleStatements:
    def test_multiple_statements_rejected(self):
        valid, errors = SQLSanitizer.validate_query(
            "SELECT 1; SELECT 2", allow_destructive=True
        )
        assert not valid
        assert any("multiple" in e.lower() for e in errors)


class TestHelperMethods:
    def test_sanitize_identifier_removes_special_chars(self):
        result = SQLSanitizer.sanitize_identifier("users; DROP TABLE")
        assert result == "usersDROPTABLE"

    def test_sanitize_identifier_keeps_underscore(self):
        result = SQLSanitizer.sanitize_identifier("user_table_1")
        assert result == "user_table_1"

    def test_is_read_only_select(self):
        assert SQLSanitizer.is_read_only_query("SELECT * FROM t")

    def test_is_read_only_explain(self):
        assert SQLSanitizer.is_read_only_query("EXPLAIN SELECT 1")

    def test_is_not_read_only_insert(self):
        assert not SQLSanitizer.is_read_only_query("INSERT INTO t VALUES (1)")

    def test_mask_dsn_hides_password(self):
        dsn = "postgresql://user:supersecret@localhost/mydb"
        masked = SQLSanitizer.mask_dsn(dsn)
        assert "supersecret" not in masked
        assert "***" in masked
        assert "user" in masked
        assert "localhost" in masked

    def test_mask_dsn_no_password_unchanged(self):
        dsn = "sqlite:///local.db"
        assert SQLSanitizer.mask_dsn(dsn) == dsn
