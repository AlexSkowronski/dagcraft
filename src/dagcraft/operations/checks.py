"""
The check operation: data quality checks inside a transform.
"""

from typing import Any

import pandas as pd

from dagcraft.exceptions import ExecutionError
from dagcraft.logs import get_logger
from dagcraft.operations.base import register_operation

logger = get_logger(__name__)


@register_operation("check")
def check(
    data: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    not_null: list[str] | None = None,
    unique: list[str] | None = None,
    accepted: dict[str, list[Any]] | None = None,
    min_rows: int | None = None,
    max_rows: int | None = None,
    warn: bool = False,
) -> pd.DataFrame:
    """
    Check the table and pass it on unchanged, or fail with every problem found.

    ``columns`` must exist; ``not_null`` columns have no missing values;
    ``unique`` columns, together, identify each row; ``accepted`` maps a
    column to its allowed values; ``min_rows`` and ``max_rows`` bound the
    row count. With ``warn``, problems are logged as a warning instead.
    """
    problems = [
        *missing_columns(data, [*(columns or []), *(not_null or []), *(unique or [])]),
        *null_values(data, not_null or []),
        *repeated_keys(data, unique or []),
        *unaccepted_values(data, accepted or {}),
        *row_count(data, min_rows, max_rows),
    ]

    if problems and warn:
        logger.warning("check found problems: %s", "; ".join(problems))
    elif problems:
        raise ExecutionError("; ".join(problems))

    return data


def missing_columns(data: pd.DataFrame, columns: list[str]) -> list[str]:
    """
    A problem if any of ``columns`` isn't in the table.
    """
    missing = sorted({column for column in columns if column not in data.columns})
    return [f"missing columns: {', '.join(missing)}"] if missing else []


def null_values(data: pd.DataFrame, columns: list[str]) -> list[str]:
    """
    A problem for each of ``columns`` with missing values.
    """
    return [
        f"{column} has {count:,} missing values"
        for column in columns
        if column in data.columns and (count := int(data[column].isna().sum()))
    ]


def repeated_keys(data: pd.DataFrame, columns: list[str]) -> list[str]:
    """
    A problem if ``columns``, together, repeat across rows.
    """
    if not columns or any(column not in data.columns for column in columns):
        return []

    repeated = data.duplicated(subset=columns, keep=False)

    if not repeated.any():
        return []

    example = data.loc[repeated, columns].iloc[0]
    values = ", ".join(f"{column}={value!r}" for column, value in example.items())
    return [
        f"{int(repeated.sum()):,} rows share {', '.join(columns)} with another "
        f"row, such as {values}"
    ]


def unaccepted_values(data: pd.DataFrame, accepted: dict[str, list[Any]]) -> list[str]:
    """
    A problem for each column holding values outside its accepted ones.
    """
    problems = []

    for column, values in accepted.items():
        if column not in data.columns:
            problems.append(f"missing columns: {column}")
            continue

        present = data[column].dropna()
        others = present[~present.isin(values)]

        if not others.empty:
            problems.append(
                f"{column} has {len(others):,} values not in {values}, "
                f"such as {others.iloc[0]!r}"
            )

    return problems


def row_count(
    data: pd.DataFrame, minimum: int | None, maximum: int | None
) -> list[str]:
    """
    A problem if the table has fewer than ``minimum`` or more than ``maximum`` rows.
    """
    rows = len(data)

    if minimum is not None and rows < minimum:
        return [f"has {rows:,} rows, fewer than {minimum:,}"]
    if maximum is not None and rows > maximum:
        return [f"has {rows:,} rows, more than {maximum:,}"]
    return []
