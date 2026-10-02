from __future__ import annotations

from pathlib import PurePath
from typing import Any, BinaryIO, ClassVar

from dagcraft.exceptions import RegistryError
from dagcraft.extras import require_extra
from dagcraft.registry import FORMATS


class Format:
    """Reads and writes one file format through open binary file objects.

    ``extensions`` lists the file suffixes this format is inferred from.
    ``modules`` and ``extra`` name optional dependencies and the dagcraft
    extra that installs them. A format with ``multiple_inputs`` can write
    several tables to one file; ``write`` then receives a dict of them.
    """

    extensions: ClassVar[tuple[str, ...]] = ()
    modules: ClassVar[tuple[str, ...]] = ()
    extra: ClassVar[str] = ""
    multiple_inputs: ClassVar[bool] = False

    def check_available(self) -> None:
        """Raise ``ConfigError`` if an optional dependency is missing."""
        if self.modules:
            require_extra(
                *self.modules,
                extra=self.extra,
                feature=f"Reading and writing {self.extensions[0]} files",
            )

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
