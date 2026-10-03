"""
Operations that combine tables or rows: joining and aggregating.
"""

from typing import Literal

import pandas as pd

from dagcraft.operations.base import register_operation


@register_operation("join", tables=("right",), source="left")
def join(
    data: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str] | None = None,
    how: Literal["inner", "left", "right", "outer", "cross"] = "inner",
    *,
    left_on: str | list[str] | None = None,
    right_on: str | list[str] | None = None,
    suffixes: list[str] | None = None,
    validate: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    | None = None,
) -> pd.DataFrame:
    """
    Join the ``left`` table with the ``right`` one on shared columns.

    ``right`` names another of the step's inputs. ``left`` names one too
    when the join comes first in a transform; later, the left side is the
    result so far. Match on ``on``, or on ``left_on`` and ``right_on`` when
    the columns are named differently. ``how`` is ``inner``, ``left``,
    ``right`` or ``outer``. ``suffixes`` tell apart other columns both sides
    have (default ``[_x, _y]``). ``validate`` fails the join unless keys
    match as expected, such as ``many_to_one``.
    """
    if suffixes is not None and len(suffixes) != 2:  # noqa: PLR2004 - left and right
        raise ValueError("suffixes takes two: one for each side, such as [_x, _y].")

    left_suffix, right_suffix = suffixes or ["_x", "_y"]
    return data.merge(
        right,
        on=on,
        how=how,
        left_on=left_on,
        right_on=right_on,
        suffixes=(left_suffix, right_suffix),
        validate=validate,
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
