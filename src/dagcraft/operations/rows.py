"""
Operations that choose and order rows.
"""

from typing import Literal

import pandas as pd

from dagcraft.operations.base import register_operation


@register_operation("filter", main="expression")
def filter_rows(data: pd.DataFrame, expression: str) -> pd.DataFrame:
    """
    Keep the rows matching ``expression``, such as ``amount > 100``.

    Written as for ``DataFrame.query``: ``and``, ``or``, ``==``, ``in``, and
    backticks around column names with spaces.
    """
    return data.query(expression)


@register_operation("drop_nulls", main="subset")
def drop_nulls(data: pd.DataFrame, subset: list[str] | None = None) -> pd.DataFrame:
    """
    Drop rows with a missing value in any of ``subset``, or in any column.
    """
    return data.dropna(subset=subset)


@register_operation("dedupe", main="subset")
def dedupe(
    data: pd.DataFrame,
    subset: list[str] | None = None,
    keep: Literal["first", "last"] = "first",
) -> pd.DataFrame:
    """
    Drop repeated rows: the same in ``subset``, or in every column.

    ``keep`` says which of the repeats stays: the ``first`` or the ``last``.
    """
    return data.drop_duplicates(subset=subset, keep=keep)


@register_operation("sort", main="by")
def sort_rows(
    data: pd.DataFrame,
    by: str | list[str],
    ascending: bool | list[bool] = True,
) -> pd.DataFrame:
    """
    Sort rows by one or more columns; ``ascending`` can be one per column.
    """
    return data.sort_values(by=by, ascending=ascending)
