"""
Operations that combine tables or rows: joining and aggregating.
"""

from typing import Any, Literal

import pandas as pd

from dagcraft.operations.base import register_operation


@register_operation("join", tables=("right",))
def join(
    data: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str],
    how: Literal["inner", "left", "right", "outer", "cross"] = "inner",
    **args: Any,
) -> pd.DataFrame:
    """
    Join another of the step's inputs, named by ``right``, on shared columns.

    ``how`` is ``inner``, ``left``, ``right`` or ``outer``; any other
    ``DataFrame.merge`` option, such as ``suffixes``, works too.
    """
    return data.merge(right, on=on, how=how, **args)


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
