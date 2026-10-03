"""
JSON documents.
"""

import json
from typing import Any, BinaryIO

from dagcraft.formats.documents import DocumentFormat, json_value, plain
from dagcraft.registry import register_format


@register_format("json")
class JSONFormat(DocumentFormat):
    """
    A JSON document, read as the dicts and lists it holds.

    Reading passes ``args`` to ``json.load``; writing passes them to
    ``json.dumps``, such as ``indent: 2``. Dates are written as ISO text.
    """

    extensions = (".json",)

    def read(self, file: BinaryIO, **args: Any) -> Any:
        return json.load(file, **args)

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        args = {"ensure_ascii": False, "default": json_value, **args}
        file.write(json.dumps(plain(data), **args).encode("utf-8"))
