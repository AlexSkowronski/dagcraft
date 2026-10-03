"""
Operations for transform steps. Importing this package registers the built-in ones.

    rows.py             filter, drop_nulls, dedupe, sort
    columns.py          select, drop, rename, cast, derive, fill_nulls
    combine.py          join, aggregate
    checks.py           check
    documents.py        flatten
    python_function.py  python: your own function
"""

from dagcraft.operations.base import Operation, register_operation
from dagcraft.operations.checks import check
from dagcraft.operations.columns import (
    cast_columns,
    derive_columns,
    drop_columns,
    fill_nulls,
    rename_columns,
    select_columns,
)
from dagcraft.operations.combine import aggregate, join
from dagcraft.operations.documents import flatten
from dagcraft.operations.python_function import python
from dagcraft.operations.rows import dedupe, drop_nulls, filter_rows, sort_rows

__all__ = [
    "Operation",
    "aggregate",
    "cast_columns",
    "check",
    "dedupe",
    "derive_columns",
    "drop_columns",
    "drop_nulls",
    "fill_nulls",
    "filter_rows",
    "flatten",
    "join",
    "python",
    "register_operation",
    "rename_columns",
    "select_columns",
    "sort_rows",
]
