"""
JSON documents.

Reading flattens nested objects into columns with ``pandas.json_normalize``
(``{"user": {"id": 1}}`` becomes a ``user.id`` column), and ``args`` go to
it: ``record_path`` and ``meta`` pick records out of a larger document.
Writing produces a list of records, one per row.
"""

import json
from typing import Any, BinaryIO

import pandas as pd

from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("json")
class JSONFormat(Format):
    """
    A JSON document: a list of records, or an object holding them.
    """

    extensions = (".json",)

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.json_normalize(json.load(file), **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        args = {"orient": "records", "date_format": "iso", "force_ascii": False, **args}
        file.write(data.to_json(**args).encode("utf-8"))
