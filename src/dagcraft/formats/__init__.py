"""File formats. Importing this package registers the built-in ones."""

from dagcraft.formats.base import Format, resolve_format
from dagcraft.formats.documents import JSONFormat, JSONLinesFormat, YAMLFormat
from dagcraft.formats.tabular import CSVFormat, ExcelFormat, ParquetFormat

__all__ = [
    "CSVFormat",
    "ExcelFormat",
    "Format",
    "JSONFormat",
    "JSONLinesFormat",
    "ParquetFormat",
    "YAMLFormat",
    "resolve_format",
]
