"""Document formats: JSON, JSON Lines and YAML.

Reading flattens nested objects into columns with ``pandas.json_normalize``
(``{"user": {"id": 1}}`` becomes a ``user.id`` column), and ``args`` go to
it: ``record_path`` and ``meta`` pick records out of a larger document.
Writing produces one record per row.
"""

from __future__ import annotations

import io
import json
from typing import Any, BinaryIO

import pandas as pd
import yaml

from dagcraft.core.config import load_yaml
from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("json")
class JSONFormat(Format):
    """A JSON document: a list of records, or an object holding them."""

    extensions = (".json",)

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.json_normalize(json.load(file), **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        args = {"orient": "records", "date_format": "iso", "force_ascii": False, **args}
        file.write(data.to_json(**args).encode("utf-8"))


@register_format("jsonl")
class JSONLinesFormat(Format):
    """JSON Lines: one JSON record per line."""

    extensions = (".jsonl", ".ndjson")

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        records = [json.loads(line) for line in file if line.strip()]
        return pd.json_normalize(records, **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        args = {"date_format": "iso", "force_ascii": False, **args}
        text = data.to_json(orient="records", lines=True, **args)
        file.write(text.encode("utf-8"))


@register_format("yaml")
class YAMLFormat(Format):
    """A YAML document, read like JSON. Only true/false are booleans."""

    extensions = (".yaml", ".yml")

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        document = load_yaml(io.StringIO(file.read().decode("utf-8")))
        return pd.json_normalize(document, **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        # Round-trip through JSON to get plain values (dates as ISO text,
        # missing values as null) that YAML can represent.
        records = json.loads(data.to_json(orient="records", date_format="iso"))
        text = yaml.safe_dump(records, sort_keys=False, allow_unicode=True, **args)
        file.write(text.encode("utf-8"))
