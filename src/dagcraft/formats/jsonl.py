"""
JSON Lines files: one JSON record per line.
"""

import json
from typing import Any, BinaryIO

from dagcraft.formats.documents import DocumentFormat, json_value, plain
from dagcraft.registry import register_format


@register_format("jsonl")
class JSONLinesFormat(DocumentFormat):
    """
    One JSON record per line, read as a list of the records.

    Blank lines are skipped. Reading passes ``args`` to ``json.loads`` for
    each line; writing passes them to ``json.dumps``. Several files read at
    once give one list of all their records.
    """

    extensions = (".jsonl", ".ndjson")

    def read(self, file: BinaryIO, **args: Any) -> list[Any]:
        return [json.loads(line, **args) for line in file if line.strip()]

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        args = {"ensure_ascii": False, "default": json_value, **args}
        records = plain(data)
        records = records if isinstance(records, list) else [records]
        text = "".join(json.dumps(record, **args) + "\n" for record in records)
        file.write(text.encode("utf-8"))

    def combine(
        self,
        parts: list[tuple[str, Any]],
        source_column: str | None,
    ) -> list[Any]:
        """
        Every file's records in one list, in path order.
        """
        documents = super().combine(parts, source_column)
        return [record for records in documents for record in records]
