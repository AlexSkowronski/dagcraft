"""Tabular file formats, read and written with pandas."""

from __future__ import annotations

from typing import Any, BinaryIO

import pandas as pd

from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("csv")
class CSVFormat(Format):
    extensions = (".csv",)

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.read_csv(file, **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        args.setdefault("index", False)
        data.to_csv(file, **args)


@register_format("parquet")
class ParquetFormat(Format):
    extensions = (".parquet", ".pq")

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.read_parquet(file, **args)

    def write(self, data: pd.DataFrame, file: BinaryIO, **args: Any) -> None:
        args.setdefault("index", False)
        data.to_parquet(file, **args)
