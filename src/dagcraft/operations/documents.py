"""
Built-in operations on documents (dicts and lists), for ``transform`` steps.
"""

from typing import Any

import pandas as pd

from dagcraft.operations.base import register_operation


@register_operation("flatten")
def flatten(data: Any, **args: Any) -> pd.DataFrame:
    """
    Turn documents into a table, with ``pandas.json_normalize``.

    ``data`` is a document or a list of them. Nested objects become dotted
    columns (``user.id``); ``record_path`` takes the rows from a list inside
    each document, ``meta`` copies document fields onto each row, and
    ``max_level`` limits how deep objects are flattened.
    """
    return pd.json_normalize(data, **args)
