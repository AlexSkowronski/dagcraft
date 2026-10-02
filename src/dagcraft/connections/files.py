from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, BinaryIO, Self

import fsspec
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.connections.base import Connection
from dagcraft.exceptions import ExecutionError
from dagcraft.formats import resolve_format

WILDCARDS = "*?["


def has_wildcards(path: str) -> bool:
    return any(character in path for character in WILDCARDS)


class FileReadOptions(BaseModel):
    """Fields of a read step that uses a file connection.

    A ``path`` with wildcards (``*``, ``?``, ``[...]``, ``**`` for any depth)
    reads every matching file into one table; ``source_column`` then adds a
    column naming each row's file.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    format: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    source_column: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def check_options(self) -> Self:
        resolve_format(self.path, self.format).check_available()

        if self.source_column is not None and not has_wildcards(self.path):
            raise ValueError("'source_column' only applies when 'path' has wildcards.")
        return self


class FileWriteOptions(BaseModel):
    """Fields of a write step that uses a file connection."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    format: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_options(self) -> Self:
        if has_wildcards(self.path):
            raise ValueError(f"A path to write can't contain wildcards ({WILDCARDS}).")

        resolve_format(self.path, self.format).check_available()
        return self


class FileConnection(Connection):
    """Base for connections to storage that holds files.

    Subclasses implement ``open_file`` and, to support wildcard paths,
    ``glob``; formats turn the files into data and back.
    """

    read_options = FileReadOptions
    write_options = FileWriteOptions

    def open_file(self, path: str, mode: str) -> AbstractContextManager[BinaryIO]:
        """Open ``path`` (relative to the connection) as ``"rb"`` or ``"wb"``."""
        raise NotImplementedError

    def glob(self, pattern: str) -> list[str]:
        """Return the files matching ``pattern``, relative to the connection."""
        raise NotImplementedError

    def read(self, options: FileReadOptions) -> Any:
        file_format = resolve_format(options.path, options.format)

        if not has_wildcards(options.path):
            with self.open_file(options.path, "rb") as file:
                return file_format.read(file, **options.args)

        paths = sorted(self.glob(options.path))

        if not paths:
            raise ExecutionError(
                f"No files in connection '{self.name}' match '{options.path}'."
            )

        frames = []

        for path in paths:
            with self.open_file(path, "rb") as file:
                frame = file_format.read(file, **options.args)

            if options.source_column is not None:
                frame[options.source_column] = path

            frames.append(frame)

        return pd.concat(frames, ignore_index=True)

    def describe(self, options: FileReadOptions | FileWriteOptions) -> str:
        return options.path

    def accepts_multiple_inputs(self, options: FileWriteOptions) -> bool:
        return resolve_format(options.path, options.format).multiple_inputs

    def write(self, data: Any, options: FileWriteOptions) -> None:
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

    def check(self) -> str:
        root = self.resolve("")

        if self.filesystem.exists(root):
            return f"{root} is reachable"
        return f"{root} doesn't exist yet; writing will create it"

    def open_file(self, path: str, mode: str) -> AbstractContextManager[BinaryIO]:
        file: AbstractContextManager[BinaryIO] = self.filesystem.open(
            self.resolve(path),
            mode,
        )
        return file

    def glob(self, pattern: str) -> list[str]:
        filesystem = self.filesystem
        # Normalise the root the same way fsspec normalises its results.
        root = filesystem._strip_protocol(self.resolve("")).rstrip("/")
        matches = filesystem.glob(self.resolve(pattern), detail=True)

        return [
            match[len(root) :].lstrip("/") if match.startswith(root) else match
            for match, info in matches.items()
            if info.get("type") == "file"
        ]
