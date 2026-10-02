"""File formats: how data is turned into bytes and back."""

from __future__ import annotations

from pathlib import PurePath
from typing import Any, BinaryIO, ClassVar

import pandas as pd

from dagcraft.exceptions import RegistryError
from dagcraft.registry import FORMATS, register_format


class Format:
    """Reads and writes one file format through open binary file objects.

    ``extensions`` lists the file suffixes this format is inferred from.
    """

    extensions: ClassVar[tuple[str, ...]] = ()

    def read(self, file: BinaryIO, **args: Any) -> Any:
        raise NotImplementedError

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        raise NotImplementedError


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


def resolve_format(path: str, name: str | None = None) -> Format:
    """Return the format called ``name``, or infer it from the path's suffix."""
    if name is not None:
        try:
            return FORMATS.get(name)()
        except RegistryError as exc:
            raise ValueError(str(exc)) from None

    suffix = PurePath(path).suffix.lower()

    for format_class in FORMATS.values():
        if suffix in format_class.extensions:
            return format_class()

    raise ValueError(
        f"Cannot infer a format from '{path}'. "
        f"Set 'format' to one of: {', '.join(FORMATS.names())}."
    )
