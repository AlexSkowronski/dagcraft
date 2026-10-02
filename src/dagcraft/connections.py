"""Connections: named, configured places that data is read from or written to."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Self

import fsspec
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.exceptions import ExecutionError
from dagcraft.formats import resolve_format
from dagcraft.registry import register_connection


class Connection:
    """Base class for connection types.

    A connection is created when the pipeline is compiled, opened the first
    time a step uses it during a run, and closed when the run ends.

    Subclasses set ``config_model`` to validate their entry in the
    ``connections`` block, and ``read_options`` / ``write_options`` to
    validate the remaining fields of read and write steps that use them.
    Leaving one as ``None`` means the connection cannot be read from or
    written to.
    """

    config_model: ClassVar[type[BaseModel]]
    read_options: ClassVar[type[BaseModel] | None] = None
    write_options: ClassVar[type[BaseModel] | None] = None

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        self.name = name
        self.config = config
        self.base_dir = base_dir

    def open(self) -> None:
        """Acquire resources, such as clients or engines."""

    def close(self) -> None:
        """Release anything acquired in ``open``."""

    def read(self, options: Any) -> Any:
        raise NotImplementedError

    def write(self, data: Any, options: Any) -> None:
        raise NotImplementedError


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
    """Base for connections backed by an fsspec filesystem.

    Subclasses implement ``create_filesystem`` and ``resolve``; reading and
    writing any registered format is handled here.
    """

    read_options = FileOptions
    write_options = FileOptions

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

    def read(self, options: FileOptions) -> Any:
        file_format = resolve_format(options.path, options.format)

        with self.filesystem.open(self.resolve(options.path), "rb") as file:
            return file_format.read(file, **options.args)

    def write(self, data: Any, options: FileOptions) -> None:
        file_format = resolve_format(options.path, options.format)

        with self.filesystem.open(self.resolve(options.path), "wb") as file:
            file_format.write(data, file, **options.args)


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str = "."


@register_connection("local")
class LocalConnection(FileConnection):
    """Files on the local filesystem.

    Step paths are relative to ``root``, and a relative ``root`` is relative
    to the directory containing the pipeline file. Parent directories are
    created when writing.
    """

    config_model = LocalConfig
    config: LocalConfig

    def create_filesystem(self) -> fsspec.AbstractFileSystem:
        return fsspec.filesystem("file", auto_mkdir=True)

    def resolve(self, path: str) -> str:
        return str(self.base_dir / self.config.root / path)
