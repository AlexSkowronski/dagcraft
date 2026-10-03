"""
Built-in operations on documents (dicts and lists), for ``transform`` steps.
"""

from typing import Any

import pandas as pd

from dagcraft.operations.base import register_operation


@register_operation("flatten")
def flatten(
    data: Any,
    record_path: str | list[str] | None = None,
    meta: list[str | list[str]] | None = None,
    max_level: int | None = None,
    sep: str = ".",
) -> pd.DataFrame:
    """
    Turn documents into a table, with ``pandas.json_normalize``.

    ``data`` is a document or a list of them. Nested objects become dotted
    columns (``user.id``); ``record_path`` takes the rows from a list inside
    each document, ``meta`` copies document fields onto each row (nested
    ones as a list, such as ``[source, system]``), ``max_level`` limits how
    deep objects are flattened, and ``sep`` joins the names of nested ones.
    """
    return pd.json_normalize(
        data,
        record_path=record_path,
        meta=meta,
        max_level=max_level,
        sep=sep,
    )
