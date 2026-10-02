from __future__ import annotations

import os

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
    created when writing.
    """

    config_model = LocalConfig
    config: LocalConfig

    def create_filesystem(self) -> fsspec.AbstractFileSystem:
        return fsspec.filesystem("file", auto_mkdir=True)

    def resolve(self, path: str) -> str:
        # normpath tidies away '..' without touching the filesystem.
        return os.path.normpath(self.base_dir / self.config.root / path)
