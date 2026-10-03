"""
Built-in operations on DataFrames, for ``transform`` steps.

Each takes its inputs by name (``data``, or ``left`` and ``right``) and the
step's ``args`` as keyword arguments.
"""

from typing import Any

import pandas as pd

from dagcraft.registry import register_operation


@register_operation("drop_nulls")
def drop_nulls(
    data: pd.DataFrame,
    subset: list[str] | None = None,
) -> pd.DataFrame:
    """
    Drop rows with a missing value, in any column or only those in ``subset``.
    """
    return data.dropna(subset=subset)


@register_operation("filter")
def filter_rows(
    data: pd.DataFrame,
    expression: str,
) -> pd.DataFrame:
    """
    Keep the rows matching ``expression``, such as ``"amount > 100"``.
    """
    return data.query(expression)


@register_operation("select")
def select_columns(
    data: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Keep only ``columns``, in that order.
    """
    return data.loc[:, columns]


@register_operation("rename")
def rename_columns(
    data: pd.DataFrame,
    columns: dict[str, str],
) -> pd.DataFrame:
    """
    Rename columns, old name to new name.
    """
    return data.rename(columns=columns)


@register_operation("sort")
def sort_rows(
    data: pd.DataFrame,
    by: str | list[str],
    ascending: bool = True,
) -> pd.DataFrame:
    """
    Sort rows by one or more columns.
    """
    return data.sort_values(
        by=by,
        ascending=ascending,
    )


@register_operation("join")
def join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str],
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Join ``left`` and ``right`` on shared columns; ``how`` and more go to merge.
    """
    return left.merge(
        right,
        on=on,
        **kwargs,
    )


@register_operation("aggregate")
def aggregate(
    data: pd.DataFrame,
    by: str | list[str],
    columns: dict[str, str],
) -> pd.DataFrame:
    """
    Group rows by ``by`` and aggregate each column with the named function.

    ``columns`` maps a column to ``sum``, ``mean``, ``count``, ``min``,
    ``max`` or any other pandas aggregation.
    """
    return data.groupby(by, as_index=False).agg(columns)
