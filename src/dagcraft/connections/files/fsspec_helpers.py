"""Opening and listing files on fsspec filesystems (local disk, Azure Blob)."""

from contextlib import AbstractContextManager
from typing import BinaryIO, cast

import fsspec


def open_binary(
    filesystem: fsspec.AbstractFileSystem,
    path: str,
    mode: str,
) -> AbstractContextManager[BinaryIO]:
    """Open ``path`` in a binary mode.

    fsspec's file objects behave like ``BinaryIO`` but aren't declared as
    one, hence the cast.
    """
    return cast("AbstractContextManager[BinaryIO]", filesystem.open(path, mode))


def glob_files(
    filesystem: fsspec.AbstractFileSystem,
    root: str,
    pattern: str,
) -> list[str]:
    """The files (not folders) matching ``pattern``, relative to ``root``.

    ``root`` and ``pattern`` are full paths on the filesystem.
    """
    # Normalise the root the same way fsspec normalises its results.
    root = cast("str", filesystem._strip_protocol(root)).rstrip("/")
    matches = cast("dict[str, dict]", filesystem.glob(pattern, detail=True))

    return [
        path[len(root) :].lstrip("/") if path.startswith(root) else path
        for path, info in matches.items()
        if info.get("type") == "file"
    ]
