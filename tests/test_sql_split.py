"""Tests for SQL statement splitting used at schema bootstrap."""

from app.core.db import _iter_sql_statements


def test_keeps_dollar_quoted_function() -> None:
    """Function bodies containing semicolons must stay one statement."""
    script = """
CREATE TABLE t (id TEXT);
CREATE OR REPLACE FUNCTION f()
RETURNS void
AS $$
BEGIN
    PERFORM 1;
END;
$$;
"""
    statements = _iter_sql_statements(script)
    assert len(statements) == 2
    assert "CREATE TABLE" in statements[0]
    assert "CREATE OR REPLACE FUNCTION" in statements[1]
