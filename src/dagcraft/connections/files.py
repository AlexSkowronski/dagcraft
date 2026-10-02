from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, BinaryIO, Self

import fsspec
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.connections.base import Connection
from dagcraft.exceptions import ExecutionError
from dagcraft.formats import resolve_format


class FileOptions(BaseModel):
    """Fields of a read or write step that uses a file connection."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    format: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_format(self) -> Self:
        resolve_format(self.path, self.format)
        return self


class FileConnection(Connection):
    """Base for connections to storage that holds files.

    Subclasses implement ``open_file``; formats turn the files into data
    and back.
    """

    read_options = FileOptions
    write_options = FileOptions

    def open_file(self, path: str, mode: str) -> AbstractContextManager[BinaryIO]:
        """Open ``path`` (relative to the connection) as ``"rb"`` or ``"wb"``."""
        raise NotImplementedError

    def read(self, options: FileOptions) -> Any:
        file_format = resolve_format(options.path, options.format)

        with self.open_file(options.path, "rb") as file:
            return file_format.read(file, **options.args)

    def write(self, data: Any, options: FileOptions) -> None:
        file_format = resolve_format(options.path, options.format)

        with self.open_file(options.path, "wb") as file:
            file_format.write(data, file, **options.args)


class FsspecConnection(FileConnection):
    """Base for file connections backed by an fsspec filesystem.

    Subclasses implement ``create_filesystem`` and ``resolve``.
    """

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        super().__init__(name, config, base_dir)
        self._filesystem: fsspec.AbstractFileSystem | None = None

    def create_filesystem(self) -> fsspec.AbstractFileSystem:
        raise NotImplementedError

    def resolve(self, path: str) -> str:
        """Turn a step's ``path`` into a full path on the filesystem."""
        raise NotImplementedError

    def open(self) -> None:
        self._filesystem = self.create_filesystem()

    def close(self) -> None:
        self._filesystem = None

    @property
    def filesystem(self) -> fsspec.AbstractFileSystem:
        if self._filesystem is None:
            raise ExecutionError(f"Connection '{self.name}' is not open.")
        return self._filesystem

    def open_file(self, path: str, mode: str) -> AbstractContextManager[BinaryIO]:
        file: AbstractContextManager[BinaryIO] = self.filesystem.open(
            self.resolve(path),
            mode,
        )
        return file
