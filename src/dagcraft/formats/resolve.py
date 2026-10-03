"""Choosing the format for a file: by name, or from its extension."""

from pathlib import PurePath

from dagcraft.exceptions import RegistryError
from dagcraft.formats.base import Format
from dagcraft.registry import FORMATS


def resolve_format(path: str, name: str | None = None) -> Format:
    """The format called ``name``, or the one ``path``'s extension implies.

    Raises ``ValueError`` if there is no such format.
    """
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
