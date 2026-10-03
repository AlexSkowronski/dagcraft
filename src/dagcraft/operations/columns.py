"""
Operations that choose, name, convert and create columns.
"""

from typing import Any

import pandas as pd

from dagcraft.operations.base import register_operation

# Friendly type names for cast, and the pandas types they mean. Whole
# numbers, booleans and text use pandas' types that allow missing values.
TYPES = {
    "int": "Int64",
    "integer": "Int64",
    "float": "float64",
    "str": "string",
    "string": "string",
    "text": "string",
    "bool": "boolean",
    "boolean": "boolean",
}


@register_operation("select", main="columns")
def select_columns(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Keep only ``columns``, in that order.
    """
    return data.loc[:, columns]


@register_operation("drop", main="columns")
def drop_columns(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Remove ``columns``.
    """
    return data.drop(columns=columns)


@register_operation("rename")
def rename_columns(data: pd.DataFrame, **columns: str) -> pd.DataFrame:
    """
    Rename columns, written as ``old name: new name``.
    """
    return data.rename(columns=columns)


@register_operation("cast")
def cast_columns(data: pd.DataFrame, **types: str) -> pd.DataFrame:
    """
    Convert columns to a type, written as ``column: type``.

    Types are ``int``, ``float``, ``str``, ``bool`` and ``datetime``, or any
    pandas type name, such as ``category`` or ``int32``.
    """
    converted = {}

    for column, name in types.items():
        if name == "datetime":
            converted[column] = pd.to_datetime(data[column])
        else:
            dtype = pd.api.types.pandas_dtype(TYPES.get(name, name))
            converted[column] = data[column].astype(dtype)

    return data.assign(**converted)


@register_operation("derive")
def derive_columns(data: pd.DataFrame, **expressions: str) -> pd.DataFrame:
    """
    Add or replace columns, written as ``column: expression``.

    Expressions are arithmetic and comparisons on other columns, as for
    ``DataFrame.eval``: ``total: price * quantity``. Each can use the ones
    before it.
    """
    data = data.copy()

    for column, expression in expressions.items():
        data[column] = data.eval(expression)
    return data


@register_operation("fill_nulls")
def fill_nulls(data: pd.DataFrame, **values: Any) -> pd.DataFrame:
    """
    Fill missing values, written as ``column: value``.
    """
    return data.fillna(value=values)
