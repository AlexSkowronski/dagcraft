"""File formats. Importing this package registers the built-in ones."""

from dagcraft.formats.base import Format, resolve_format
from dagcraft.formats.tabular import CSVFormat, ParquetFormat

__all__ = [
    "CSVFormat",
    "Format",
    "ParquetFormat",
    "resolve_format",
]
