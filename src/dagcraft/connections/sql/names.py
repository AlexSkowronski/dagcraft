"""Table and column names in pipeline files, and quoting them for a database."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlalchemy as sa


def split_table(table: str) -> tuple[str | None, str]:
    """Split ``name`` or ``schema.name`` into its schema and name."""
    match table.split("."):
        case [name] if name:
            return None, name
        case [schema, name] if schema and name:
            return schema, name

    raise ValueError(f"Table '{table}' should be written as 'name' or 'schema.name'.")


def quote_table(engine: sa.Engine, table: str) -> str:
    """``schema.table`` quoted by the database's own rules, for use in SQL text."""
    preparer = engine.dialect.identifier_preparer
    schema, name = split_table(table)
    quoted = preparer.quote(name)

    if schema is not None:
        quoted = f"{preparer.quote_schema(schema)}.{quoted}"
    return quoted


def quote_column(engine: sa.Engine, column: str) -> str:
    """``column`` quoted by the database's own rules, for use in SQL text."""
    return engine.dialect.identifier_preparer.quote(column)
