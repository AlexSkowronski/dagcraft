from __future__ import annotations

from pathlib import PurePath
from typing import Any, BinaryIO, ClassVar

from dagcraft.exceptions import RegistryError
from dagcraft.registry import FORMATS


class Format:
    """Reads and writes one file format through open binary file objects.

    ``extensions`` lists the file suffixes this format is inferred from.
    """

    extensions: ClassVar[tuple[str, ...]] = ()

    def read(self, file: BinaryIO, **args: Any) -> Any:
        raise NotImplementedError

    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        raise NotImplementedError


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
