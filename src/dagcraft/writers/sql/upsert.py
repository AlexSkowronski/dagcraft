"""
Upserting: replacing the rows whose keys match, and adding the rest.

The SQL is portable, so it works on any database SQLAlchemy supports and
needs no unique constraint on the table: the rows go into a staging table
beside the target, target rows with matching keys are deleted, and the
staged rows are inserted, all in one transaction, so a failure leaves the
table's rows as they were. The staging table is dropped either way.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

from dagcraft.connections.sql.names import split_table
from dagcraft.exceptions import ExecutionError
from dagcraft.logs import get_logger

if TYPE_CHECKING:
    import sqlalchemy as sa

logger = get_logger(__name__)


@dataclass(frozen=True)
class UpsertCounts:
    """
    How many rows an upsert replaced, and how many it added.
    """

    replaced: int
    added: int


def upsert(
    engine: sa.Engine,
    data: pd.DataFrame,
    table: str,
    keys: list[str],
    args: dict[str, Any],
) -> UpsertCounts:
    """
    Write ``data`` to ``table``, replacing the rows whose ``keys`` match.

    A missing table is created. Raises ``ExecutionError``, before writing
    anything, if the keys can't identify each row (missing, empty or
    repeated) or the data has columns the table doesn't.
    """
    import sqlalchemy as sa  # noqa: PLC0415

    check_keys(data, keys)
    schema, name = split_table(table)
    args = {"index": False, **args}
    staging = f"dagcraft_staging_{uuid.uuid4().hex[:8]}"

    try:
        with engine.begin() as connection:
            inspector = sa.inspect(connection)

            if not inspector.has_table(name, schema=schema):
                data.to_sql(name, connection, schema=schema, **args)
                return UpsertCounts(replaced=0, added=len(data))

            check_columns(data, inspector.get_columns(name, schema=schema), table)
            data.to_sql(staging, connection, schema=schema, **args)
            replaced = merge_staged(connection, name, staging, schema, data, keys)
            drop_table(connection, staging, schema)
    except Exception:
        # Not every driver undoes CREATE TABLE on rollback (Python's sqlite3
        # doesn't), so make sure the staging table is gone.
        drop_leftover(engine, staging, schema)
        raise

    return UpsertCounts(replaced=replaced, added=len(data) - replaced)


def merge_staged(
    connection: sa.Connection,
    table: str,
    staging: str,
    schema: str | None,
    data: pd.DataFrame,
    keys: list[str],
) -> int:
    """
    Swap the staged rows into ``table``; return how many replaced a row.
    """
    import sqlalchemy as sa  # noqa: PLC0415

    columns = [str(column) for column in data.columns]
    target = sa.table(table, *map(sa.column, columns), schema=schema)
    staged = sa.table(staging, *map(sa.column, columns), schema=schema)
    same_keys = sa.and_(*(target.c[key] == staged.c[key] for key in keys))

    replaced = connection.execute(
        sa.select(sa.func.count())
        .select_from(staged)
        .where(sa.exists().where(same_keys))
    ).scalar_one()
    connection.execute(sa.delete(target).where(sa.exists().where(same_keys)))
    connection.execute(sa.insert(target).from_select(columns, sa.select(*staged.c)))
    return replaced


def drop_table(
    connection: sa.Connection | sa.Engine,
    table: str,
    schema: str | None,
) -> None:
    """
    Drop ``table`` if it exists.
    """
    import sqlalchemy as sa  # noqa: PLC0415

    sa.Table(table, sa.MetaData(), schema=schema).drop(connection, checkfirst=True)


def drop_leftover(engine: sa.Engine, staging: str, schema: str | None) -> None:
    """
    Drop a staging table a failed upsert left behind; warn if that fails too.
    """
    try:
        drop_table(engine, staging, schema)
    except Exception:
        logger.warning(
            "Couldn't drop the staging table %s; drop it by hand.",
            staging,
            exc_info=True,
        )


def check_keys(data: pd.DataFrame, keys: list[str]) -> None:
    """
    Raise ``ExecutionError`` unless ``keys`` identify each row of ``data``.
    """
    missing = [key for key in keys if key not in data.columns]

    if missing:
        raise ExecutionError(f"Upsert keys not in the data: {', '.join(missing)}.")

    empty = data[keys].isna().any(axis=1)

    if empty.any():
        raise ExecutionError(
            f"{empty.sum():,} rows have no value in a key column "
            f"({', '.join(keys)}), so they can't be matched."
        )

    repeated = data.duplicated(subset=keys, keep=False)

    if repeated.any():
        example = data.loc[repeated, keys].iloc[0]
        values = ", ".join(f"{key}={value!r}" for key, value in example.items())
        raise ExecutionError(
            f"{repeated.sum():,} rows share their keys with another row, "
            f"such as {values}."
        )


def check_columns(
    data: pd.DataFrame,
    table_columns: list[Any],
    table: str,
) -> None:
    """
    Raise ``ExecutionError`` if ``data`` has columns the table doesn't.

    Names are compared ignoring case, as SQL Server does by default.
    """
    known = {str(column["name"]).lower() for column in table_columns}
    unknown = [
        str(column) for column in data.columns if str(column).lower() not in known
    ]

    if unknown:
        raise ExecutionError(
            f"Table {table} has no column {', '.join(unknown)}; an upsert "
            "writes every column of the data."
        )
