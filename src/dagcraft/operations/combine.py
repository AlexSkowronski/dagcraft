"""
Operations that combine tables or rows: joining and aggregating.
"""

from typing import Any, Literal

import pandas as pd

from dagcraft.operations.base import register_operation


@register_operation("join", tables=("right",), source="left")
def join(
    data: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str],
    how: Literal["inner", "left", "right", "outer", "cross"] = "inner",
    **args: Any,
) -> pd.DataFrame:
    """
    Join the ``left`` table with the ``right`` one on shared columns.

    ``right`` names another of the step's inputs. ``left`` names one too
    when the join comes first in a transform; later, the left side is the
    result so far. ``how`` is ``inner``, ``left``, ``right`` or ``outer``;
    any other ``DataFrame.merge`` option, such as ``suffixes``, works too.
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
