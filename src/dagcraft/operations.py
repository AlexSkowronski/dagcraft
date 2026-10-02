from __future__ import annotations

from typing import Any

import pandas as pd

from dagcraft.registry import register_operation


@register_operation("drop_nulls")
def drop_nulls(
    data: pd.DataFrame,
    subset: list[str] | None = None,
) -> pd.DataFrame:
    return data.dropna(subset=subset)


@register_operation("filter")
def filter_rows(
    data: pd.DataFrame,
    expression: str,
) -> pd.DataFrame:
    return data.query(expression)


@register_operation("select")
def select_columns(
    data: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    return data.loc[:, columns]


@register_operation("rename")
def rename_columns(
    data: pd.DataFrame,
    columns: dict[str, str],
) -> pd.DataFrame:
    return data.rename(columns=columns)


@register_operation("sort")
def sort_rows(
    data: pd.DataFrame,
    by: str | list[str],
    ascending: bool = True,
) -> pd.DataFrame:
    return data.sort_values(
        by=by,
        ascending=ascending,
    )


@register_operation("join")
def join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str],
    how: str = "inner",
    **kwargs: Any,
) -> pd.DataFrame:
    return left.merge(
        right,
        on=on,
        how=how,
        **kwargs,
    )