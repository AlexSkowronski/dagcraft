"""
YAML documents.
"""

from typing import Any, BinaryIO

import yaml

from dagcraft.formats.documents import DocumentFormat, plain
from dagcraft.registry import register_format
from dagcraft.yaml_loader import load_yaml


@register_format("yaml")
class YAMLFormat(DocumentFormat):
    """
    A YAML document, read as the dicts and lists it holds.

    Only true/false are booleans, as in YAML 1.2. Writing passes ``args`` to
    ``yaml.safe_dump``.
    """

    extensions = (".yaml", ".yml")

    def check_args(self, args: dict[str, Any]) -> None:
        super().check_args(args)

        if args:
            raise ValueError("Reading YAML takes no args.")

    def read(self, file: BinaryIO, **args: Any) -> Any:
        return load_yaml(file.read().decode("utf-8"))

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        args = {"sort_keys": False, "allow_unicode": True, **args}
        file.write(yaml.safe_dump(plain(data), **args).encode("utf-8"))
