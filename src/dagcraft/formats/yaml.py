"""YAML documents, read and written like JSON."""

import json
from typing import Any, BinaryIO

import pandas as pd
import yaml

from dagcraft.formats.base import Format
from dagcraft.registry import register_format
from dagcraft.yaml_loader import load_yaml


@register_format("yaml")
class YAMLFormat(Format):
    """A YAML document, flattened like JSON. Only true/false are booleans."""

    extensions = (".yaml", ".yml")

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.json_normalize(load_yaml(file.read().decode("utf-8")), **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        # Round-trip through JSON to get plain values (dates as ISO text,
        # missing values as null) that YAML can represent.
        records = json.loads(data.to_json(orient="records", date_format="iso"))
        text = yaml.safe_dump(records, sort_keys=False, allow_unicode=True, **args)
        file.write(text.encode("utf-8"))
