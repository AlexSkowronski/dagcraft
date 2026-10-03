"""
File formats: how a file becomes a table. Importing registers the built-in ones.
"""

from dagcraft.formats.base import Format
from dagcraft.formats.csv import CSVFormat
from dagcraft.formats.excel import ExcelFormat
from dagcraft.formats.json import JSONFormat
from dagcraft.formats.jsonl import JSONLinesFormat
from dagcraft.formats.parquet import ParquetFormat
from dagcraft.formats.resolve import resolve_format
from dagcraft.formats.yaml import YAMLFormat

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
