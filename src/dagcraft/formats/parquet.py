"""
Parquet files.
"""

from typing import Any, BinaryIO

import pandas as pd

from dagcraft.data import require_table
from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("parquet")
class ParquetFormat(Format):
    """
    Columnar Parquet, through pyarrow; ``args`` go to pandas.
    """

    extensions = (".parquet", ".pq")

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.read_parquet(file, **args)

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        args.setdefault("index", False)
        require_table(data, "A parquet file").to_parquet(file, **args)
