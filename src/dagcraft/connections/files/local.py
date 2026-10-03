"""
The ``local`` connection type: files on this machine.
"""

import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

import fsspec

from dagcraft.config.connections import LocalConfig
from dagcraft.connections.files.base import FileConnection, FileMode
from dagcraft.connections.files.fsspec_helpers import glob_files, open_binary
from dagcraft.registry import register_connection


@register_connection("local")
class LocalConnection(FileConnection):
    """
    Files on the local filesystem.

    Step paths are relative to ``root``, and a relative ``root`` is relative
    to the folder you run from. Parent folders are
    created when writing, and a file is written under a temporary name and
    only then put in place, so a failed write leaves the old file untouched.
    """

    config_model = LocalConfig
    config: LocalConfig

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        super().__init__(name, config, base_dir)
        self._filesystem: fsspec.AbstractFileSystem | None = None

    def open(self) -> None:
        self._filesystem = fsspec.filesystem("file", auto_mkdir=True)

    def close(self) -> None:
        self._filesystem = None

    @property
    def filesystem(self) -> fsspec.AbstractFileSystem:
        """
        The open filesystem; raises if the connection isn't open.
        """
        if self._filesystem is None:
            raise self.not_open()
        return self._filesystem

    def check(self) -> str:
        root = self.resolve("")

        if self.filesystem.exists(root):
            return f"{root} is reachable"
        return f"{root} doesn't exist yet; writing will create it"

    def resolve(self, path: str) -> str:
        """
        The full path of ``path``, a path relative to the connection.
        """
        # normpath tidies away '..' without touching the filesystem.
        return os.path.normpath(self.base_dir / self.config.root / path)

    @contextmanager
    def open_file(self, path: str, mode: FileMode) -> Generator[BinaryIO]:
        if mode == "rb":
            with open_binary(self.filesystem, self.resolve(path), mode) as file:
                yield file
            return

        target = Path(self.resolve(path))
        temporary = target.with_name(f"{target.name}.{uuid.uuid4().hex[:8]}.tmp")

        try:
            with open_binary(self.filesystem, str(temporary), mode) as file:
                yield file
            temporary.replace(target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def glob(self, pattern: str) -> list[str]:
        return glob_files(self.filesystem, self.resolve(""), self.resolve(pattern))
