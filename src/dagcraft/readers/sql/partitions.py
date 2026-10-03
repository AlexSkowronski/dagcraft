"""
Partitioned reads: splitting one big read into ranges read at the same time.

Each part runs on its own pooled database connection in its own thread, so
a large table comes back several times faster than through one connection.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pandas as pd

from dagcraft.config.readers import SQLPartition
from dagcraft.connections.sql.names import quote_column, quote_table
from dagcraft.data import describe_data
from dagcraft.exceptions import ExecutionError
from dagcraft.logs import get_logger
from dagcraft.readers.sql.query import read_query

if TYPE_CHECKING:
    import sqlalchemy as sa

logger = get_logger(__name__)


@dataclass(frozen=True)
class Part:
    """
    One query of a partitioned read, and the range it covers.
    """

    query: str
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""


def table_parts(
    engine: sa.Engine,
    table: str,
    partition: SQLPartition,
) -> list[Part] | None:
    """
    Parts covering every row of ``table``, ranged by ``partition.column``.

    The range comes from the column's MIN and MAX unless ``partition`` sets
    it. A last part reads the rows where the column is NULL. Returns
    ``None`` when there is nothing to split by (an empty table, or only
    NULLs), meaning the table should be read whole.
    """
    source = quote_table(engine, table)
    column = quote_column(engine, partition.column or "")
    lower, upper = partition.lower, partition.upper

    if lower is None or upper is None:
        lower, upper = column_range(engine, source, column)

    if lower is None or upper is None:
        return None

    # Names come from the pipeline file, quoted by the database's own rules;
    # values are bound parameters.
    query = (
        f"SELECT * FROM {source} "  # noqa: S608
        f"WHERE {column} BETWEEN :partition_start AND :partition_end"
    )
    nulls = Part(f"SELECT * FROM {source} WHERE {column} IS NULL", label="NULL")  # noqa: S608
    return [*range_parts(query, {}, lower, upper, partition.parts), nulls]


def range_parts(
    query: str,
    params: dict[str, Any],
    lower: int,
    upper: int,
    parts: int,
) -> list[Part]:
    """
    ``query`` once per range of ``lower..upper``, filling the placeholders.
    """
    return [
        Part(
            query,
            {**params, "partition_start": start, "partition_end": end},
            f"{start}..{end}",
        )
        for start, end in split_range(lower, upper, parts)
    ]


def read_parts(
    engine: sa.Engine,
    parts: list[Part],
    args: dict[str, Any],
) -> pd.DataFrame:
    """
    Run every part at once, each on its own connection, then combine them.
    """

    def read_part(number: int, part: Part) -> pd.DataFrame:
        frame = read_query(engine, part.query, part.params, args)
        logger.debug(
            "read part %d of %d (%s): %s",
            number,
            len(parts),
            part.label,
            describe_data(frame),
        )
        return frame

    with ThreadPoolExecutor(len(parts), thread_name_prefix="dagcraft-sql") as pool:
        # Each thread gets a copy of the context, so its logs name the step.
        futures = [
            pool.submit(contextvars.copy_context().run, read_part, number, part)
            for number, part in enumerate(parts, start=1)
        ]
        frames = [future.result() for future in futures]

    # The NULL part's key column is all-empty (object dtype); infer types
    # again so the result matches an unpartitioned read.
    return pd.concat(frames, ignore_index=True).infer_objects()


def column_range(
    engine: sa.Engine,
    source: str,
    column: str,
) -> tuple[int | None, int | None]:
    """
    The smallest and largest value of ``column``; ``None`` if it has none.
    """
    import sqlalchemy as sa  # noqa: PLC0415

    with engine.connect() as connection:
        # Names quoted by the database's own rules, as above.
        bounds = f"SELECT MIN({column}), MAX({column}) FROM {source}"  # noqa: S608
        lower, upper = connection.execute(sa.text(bounds)).one()

    return whole_number(lower, column), whole_number(upper, column)


def split_range(lower: int, upper: int, parts: int) -> list[tuple[int, int]]:
    """
    Split ``lower..upper`` (inclusive) into up to ``parts`` similar ranges.
    """
    total = upper - lower + 1
    parts = min(parts, total)
    size, extra = divmod(total, parts)
    ranges = []
    start = lower

    for index in range(parts):
        end = start + size - 1 + (1 if index < extra else 0)
        ranges.append((start, end))
        start = end + 1

    return ranges


def whole_number(value: Any, column: str) -> int | None:
    """
    ``value`` as an int, for a partition boundary.
    """
    if value is None:
        return None

    if isinstance(value, int) and not isinstance(value, bool):
        return value

    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)

    raise ExecutionError(
        f"Partition column {column} must hold whole numbers, "
        f"not {type(value).__name__}."
    )
