from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import fsspec
from pydantic import BaseModel, ConfigDict

from dagcraft.connections.files import FsspecConnection
from dagcraft.registry import register_connection


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str = "."


@register_connection("local")
class LocalConnection(FsspecConnection):
    """Files on the local filesystem.

    Step paths are relative to ``root``, and a relative ``root`` is relative
    to the directory containing the pipeline file. Parent directories are
    created when writing, and a file is written under a temporary name and
    only then put in place, so a failed write leaves the old file untouched.
    """

    config_model = LocalConfig
    config: LocalConfig

    def create_filesystem(self) -> fsspec.AbstractFileSystem:
        return fsspec.filesystem("file", auto_mkdir=True)

    def resolve(self, path: str) -> str:
        # normpath tidies away '..' without touching the filesystem.
        return os.path.normpath(self.base_dir / self.config.root / path)

    @contextmanager
    def open_file(self, path: str, mode: str) -> Iterator[BinaryIO]:
        if mode != "wb":
            with super().open_file(path, mode) as file:
                yield file
            return

        target = Path(self.resolve(path))
        temporary = target.with_name(f"{target.name}.{uuid.uuid4().hex[:8]}.tmp")

        try:
            with self.filesystem.open(str(temporary), "wb") as file:
                yield file
            temporary.replace(target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
