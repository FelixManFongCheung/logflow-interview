"""Postgres connection pool and schema bootstrap."""

from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    """Return the process-wide connection pool."""
    if _pool is None:
        raise RuntimeError("database pool is not initialized")
    return _pool


async def init_db() -> None:
    """Open the pool and apply schema (idempotent)."""
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=settings.postgres_dsn,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row, "autocommit": True},
        open=False,
    )
    await _pool.open()
    schema_sql = SCHEMA_PATH.read_text()
    async with _pool.connection() as conn:
        for statement in _iter_sql_statements(schema_sql):
            await conn.execute(statement)


async def close_db() -> None:
    """Close the pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def vector_literal(values: list[float]) -> str:
    """Format a Python list as a pgvector literal."""
    return "[" + ",".join(str(v) for v in values) + "]"


def _iter_sql_statements(script: str) -> list[str]:
    """Split a SQL file into statements, keeping dollar-quoted function bodies intact."""
    statements: list[str] = []
    current: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        current.append(line)
        if not in_dollar and line.strip().endswith(";"):
            statement = "\n".join(current).strip()
            if statement and not statement.startswith("--"):
                statements.append(statement)
            current = []
    rest = "\n".join(current).strip()
    if rest:
        statements.append(rest)
    return statements
