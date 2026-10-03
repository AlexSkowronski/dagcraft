"""
What steps pass between them: tables (DataFrames) or documents (dicts, lists).
"""

from typing import Any

import pandas as pd

from dagcraft.exceptions import ExecutionError


def describe_data(value: Any) -> str:
    """
    A short description of a step's output for logs: its size, or its type.
    """
    if isinstance(value, pd.DataFrame):
        rows, columns = value.shape
        return f"{rows:,} rows x {columns:,} columns"

    if isinstance(value, dict) and value:
        if all(isinstance(item, pd.DataFrame) for item in value.values()):
            return f"{len(value)} tables ({', '.join(map(str, value))})"
        return f"an object with {count(len(value), 'key')}"

    if isinstance(value, list):
        return f"a list of {count(len(value), 'item')}"

    if value is None:
        return "no output"

    return type(value).__name__


def is_empty(value: Any) -> bool:
    """
    Whether ``value`` holds nothing: no rows, no items, or None.
    """
    if value is None:
        return True
    if isinstance(value, pd.DataFrame):
        return value.empty or len(value) == 0
    if isinstance(value, (list, tuple, dict)):
        return not value
    return False


def count(number: int, noun: str) -> str:
    """
    ``number`` and ``noun``, made plural unless it's 1: "1 item", "2 items".
    """
    return f"{number:,} {noun}{'' if number == 1 else 's'}"


def require_table(value: Any, target: str) -> pd.DataFrame:
    """
    ``value`` if it's a DataFrame; else raise ``ExecutionError`` saying why.

    ``target`` names what needs the table, such as "A csv file".
    """
    if isinstance(value, pd.DataFrame):
        return value

    raise ExecutionError(
        f"{target} needs a table (a DataFrame), not {describe_data(value)}. "
        "Turn documents into one with the flatten operation or a python step."
    )
