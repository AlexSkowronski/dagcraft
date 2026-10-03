"""
What the document formats (JSON, JSON Lines, YAML) have in common.
"""

import datetime
import decimal
import json
from typing import Any

import pandas as pd

from dagcraft.exceptions import ExecutionError
from dagcraft.formats.base import Format

# pandas.json_normalize arguments, which belong to the flatten operation.
FLATTEN_ARGS = {
    "record_path",
    "meta",
    "meta_prefix",
    "record_prefix",
    "max_level",
    "sep",
}


class DocumentFormat(Format):
    """
    Files holding documents: read and written as plain Python data.

    Reading gives what the file holds (dicts, lists, strings, numbers,
    booleans, None) for your own functions to work through; the
    ``flatten`` operation turns documents into a table when you want one.
    Writing takes plain data as it is, or a DataFrame as one record per row.
    """

    def check_args(self, args: dict[str, Any]) -> None:
        flatten_args = sorted(FLATTEN_ARGS & set(args))

        if flatten_args:
            raise ValueError(
                f"{', '.join(flatten_args)} turn documents into a table, which is "
                "the flatten operation's job: read the file as it is, then add a "
                "transform step with a flatten operation taking these options."
            )

    def combine(
        self,
        parts: list[tuple[str, Any]],
        source_column: str | None,
    ) -> list[Any]:
        """
        The documents as a list, in path order.

        With ``source_column``, each object (or each object in a list) gets
        that key, naming its file.
        """
        documents = []

        for path, document in parts:
            if source_column is not None:
                name_source(document, source_column, path)
            documents.append(document)

        return documents


def name_source(document: Any, key: str, path: str) -> None:
    """
    Add ``key: path`` to ``document``, or to each object in it if it's a list.
    """
    objects = document if isinstance(document, list) else [document]

    for item in objects:
        if not isinstance(item, dict):
            raise ExecutionError(
                f"source_column needs {path} to hold objects, but it holds "
                f"a {type(item).__name__}."
            )
        item[key] = path


def plain(data: Any) -> Any:
    """
    ``data`` as plain Python values: a DataFrame becomes a list of records.

    Dates become ISO text and missing values None, as JSON has them.
    """
    if isinstance(data, pd.DataFrame):
        return json.loads(data.to_json(orient="records", date_format="iso"))
    return data


def json_value(value: Any) -> Any:
    """
    For ``json.dumps``: values JSON has no type for, as ones it has.
    """
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f"Can't write a {type(value).__name__} as JSON.")
