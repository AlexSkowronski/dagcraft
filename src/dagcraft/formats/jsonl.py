"""JSON Lines files: one JSON record per line."""

import json
from typing import Any, BinaryIO

import pandas as pd

from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("jsonl")
class JSONLinesFormat(Format):
    """One JSON record per line, flattened like JSON documents."""

    extensions = (".jsonl", ".ndjson")

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        records = [json.loads(line) for line in file if line.strip()]
        return pd.json_normalize(records, **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        args = {"date_format": "iso", "force_ascii": False, **args}
        text = data.to_json(orient="records", lines=True, **args)
        file.write(text.encode("utf-8"))
