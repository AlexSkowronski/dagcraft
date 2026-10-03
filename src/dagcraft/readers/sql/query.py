"""Running a query or reading a whole table into a DataFrame."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from dagcraft.connections.sql.names import split_table
from dagcraft.readers.sql.query_text import escape_non_code_colons

if TYPE_CHECKING:
    import sqlalchemy as sa


def read_query(
    engine: sa.Engine,
    query: str,
    params: dict[str, Any],
    args: dict[str, Any],
) -> pd.DataFrame:
    """Run ``query`` with ``params`` filling its ``:name`` placeholders."""
    import sqlalchemy as sa  # noqa: PLC0415

    with engine.connect() as connection:
        return pd.read_sql(
            sa.text(escape_non_code_colons(query)),
            connection,
            params=params,
            **args,
        )


def read_table(engine: sa.Engine, table: str, args: dict[str, Any]) -> pd.DataFrame:
    """Read every row of ``table`` (``name`` or ``schema.name``)."""
    schema, name = split_table(table)

    with engine.connect() as connection:
        return pd.read_sql_table(name, connection, schema=schema, **args)


def load_query_file(base_dir: Path, query_file: str) -> str:
    """The text of a ``.sql`` file; raises ``ValueError`` if it's missing."""
    path = base_dir / query_file

    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(
            f"Query file '{query_file}' not found (looked for {path})."
        ) from None
