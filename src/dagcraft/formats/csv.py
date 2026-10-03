"""
CSV files.
"""

from typing import Any, BinaryIO

import pandas as pd

from dagcraft.data import require_table
from dagcraft.formats.base import Format
from dagcraft.registry import register_format


@register_format("csv")
class CSVFormat(Format):
    """
    Comma-separated values; ``args`` go to ``read_csv`` and ``to_csv``.
    """

    extensions = (".csv",)

    def read(self, file: BinaryIO, **args: Any) -> pd.DataFrame:
        return pd.read_csv(file, **args)

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        args.setdefault("index", False)
        require_table(data, "A csv file").to_csv(file, **args)
