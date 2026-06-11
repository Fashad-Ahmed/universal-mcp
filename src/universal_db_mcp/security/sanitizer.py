"""SQL injection prevention and query validation."""

import re
import sqlparse
from typing import List, Tuple


class SQLSanitizer:
    """Multi-layer SQL query sanitizer with injection prevention."""

    DESTRUCTIVE_KEYWORDS = {
        "DROP",
        "DELETE",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "INSERT",
        "UPDATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "MERGE",
        "ATTACH",
        "DETACH",
        "SET",
        "CALL",
    }

    DANGEROUS_PATTERNS = [
        re.compile(r";\s*(drop|delete|truncate|alter)\s+", re.IGNORECASE),
        re.compile(r"union\s+select", re.IGNORECASE),
        re.compile(r"--"),
        re.compile(r"/\*"),
        re.compile(r"xp_", re.IGNORECASE),
        re.compile(r"exec\s*\(", re.IGNORECASE),
        re.compile(r"execute\s*\(", re.IGNORECASE),
        re.compile(r"sleep\s*\(", re.IGNORECASE),
        re.compile(r"waitfor\s+delay", re.IGNORECASE),
        re.compile(r"benchmark\s*\(", re.IGNORECASE),
    ]

    @classmethod
    def validate_query(cls, query: str, allow_destructive: bool = False) -> Tuple[bool, List[str]]:
        """
        Validate if a query is safe to execute.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: List[str] = []

        if not query or not query.strip():
            errors.append("Query cannot be empty")
            return False, errors

        try:
            parsed = sqlparse.parse(query)
        except Exception as e:
            errors.append(f"Failed to parse SQL: {e}")
            return False, errors

        if not parsed:
            errors.append("Invalid SQL query")
            return False, errors

        if len(parsed) > 1:
            errors.append("Multiple SQL statements not allowed")

        statement = parsed[0]

        if not allow_destructive:
            for keyword in cls._extract_statement_keywords(statement):
                if keyword.upper() in cls.DESTRUCTIVE_KEYWORDS:
                    errors.append(
                        f"Destructive operation '{keyword.upper()}' not allowed in read-only mode"
                    )

        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(query):
                errors.append(f"Potentially dangerous SQL pattern detected: {pattern.pattern}")

        single_quotes = query.count("'")
        if single_quotes % 2 != 0:
            errors.append("Unbalanced single quotes detected")

        return len(errors) == 0, errors

    @classmethod
    def _extract_statement_keywords(cls, statement: sqlparse.sql.Statement) -> List[str]:
        """Extract every DML/DDL/keyword token in the statement (top-level, including
        verbs hidden inside CTEs, e.g. `WITH x AS (...) DELETE FROM ...`)."""
        keywords: List[str] = []
        for token in statement.flatten():
            if token.ttype in (
                sqlparse.tokens.Keyword.DML,
                sqlparse.tokens.Keyword.DDL,
                sqlparse.tokens.Keyword,
            ):
                keywords.append(str(token.value))
        if not keywords:
            first = statement.token_first(skip_ws=True, skip_cm=True)
            if first is not None and first.ttype is None:
                val = str(first).strip().split()[0] if str(first).strip() else ""
                if val:
                    keywords.append(val)
        return keywords

    @classmethod
    def check_complexity(cls, query: str, max_joins: int = 5) -> Tuple[bool, List[str]]:
        """
        Check query for complexity issues.

        Returns:
            Tuple of (is_ok, list_of_warnings)
        """
        warnings: List[str] = []

        join_count = len(re.findall(r"\bjoin\b", query, re.IGNORECASE))
        if join_count > max_joins:
            warnings.append(
                f"Query has {join_count} JOINs, exceeding max_joins={max_joins}"
            )

        if re.search(r"select\s+\*", query, re.IGNORECASE):
            if not re.search(r"\b(where|limit)\b", query, re.IGNORECASE):
                warnings.append(
                    "SELECT * without WHERE or LIMIT clause may return excessive rows"
                )

        return len(warnings) == 0, warnings

    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """Remove non-alphanumeric chars (except underscore) from identifiers."""
        return re.sub(r"[^a-zA-Z0-9_]", "", identifier)

    @classmethod
    def is_read_only_query(cls, query: str) -> bool:
        """Check if query is read-only (SELECT/EXPLAIN/SHOW/DESCRIBE), including
        CTEs that don't hide a data-modifying statement (e.g. `WITH ... DELETE ...`)."""
        read_only_ops = {"SELECT", "EXPLAIN", "SHOW", "DESCRIBE", "DESC", "WITH"}
        parsed = sqlparse.parse(query)
        if not parsed:
            return False
        statement = parsed[0]
        first = statement.token_first(skip_ws=True, skip_cm=True)
        if first is None:
            return False
        if str(first.value).upper() not in read_only_ops:
            return False
        return not any(
            kw.upper() in cls.DESTRUCTIVE_KEYWORDS
            for kw in cls._extract_statement_keywords(statement)
        )

    @staticmethod
    def mask_dsn(dsn: str) -> str:
        """Remove password from DSN for safe logging."""
        return re.sub(r"(://[^:]+:)(.+)(@[^@/]+)", r"\1***\3", dsn)
