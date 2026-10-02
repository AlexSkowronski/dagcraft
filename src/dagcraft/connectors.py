from __future__ import annotations

from typing import Any

import pandas as pd

from dagcraft.registry import register_connector


@register_connector("csv")
class CSVConnector:
    def read(self, **kwargs: Any) -> pd.DataFrame:
        return pd.read_csv(**kwargs)

    def write(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> pd.DataFrame:
        data.to_csv(**kwargs)
        return data


@register_connector("parquet")
class ParquetConnector:
    def read(self, **kwargs: Any) -> pd.DataFrame:
        return pd.read_parquet(**kwargs)

    def write(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> pd.DataFrame:
        data.to_parquet(**kwargs)
        return data
