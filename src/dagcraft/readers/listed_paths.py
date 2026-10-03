"""
The files another step lists for a read: a list of paths, or a table of them.
"""

from typing import Any

import pandas as pd

from dagcraft.data import count, describe_data
from dagcraft.exceptions import ExecutionError


def listed_paths(listed: Any, column: str | None) -> list[str]:
    """
    The paths in ``listed``: a list of them, or a table with them in ``column``.

    A table with one column needs no ``column``. Raises ``ExecutionError``
    for anything else, or for missing paths.
    """
    if isinstance(listed, pd.DataFrame):
        values = column_values(listed, column)
    elif isinstance(listed, pd.Series):
        values = listed.tolist()
    elif isinstance(listed, (list, tuple)):
        values = list(listed)
    elif isinstance(listed, str):
        values = [listed]
    else:
        raise ExecutionError(
            f"The 'paths' input should be a list of paths or a table of them, "
            f"not {describe_data(listed)}."
        )

    missing = [value for value in values if not isinstance(value, str) or not value]

    if missing:
        raise ExecutionError(
            f"{count(len(missing), 'path')} in the 'paths' input "
            f"{'is' if len(missing) == 1 else 'are'} missing or not text."
        )

    return values


def column_values(table: pd.DataFrame, column: str | None) -> list[Any]:
    """
    The values in ``column`` of ``table``, or in its only column.
    """
    if column is None:
        if len(table.columns) != 1:
            raise ExecutionError(
                f"The 'paths' input is a table with {len(table.columns)} columns: "
                "set 'path_column' to the one holding the paths."
            )
        column = str(table.columns[0])

    if column not in table.columns:
        raise ExecutionError(
            f"path_column '{column}' isn't in the 'paths' table; it has "
            f"{', '.join(map(str, table.columns))}."
        )

    return table[column].tolist()
