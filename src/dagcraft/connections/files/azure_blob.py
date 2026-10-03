"""The ``azure_blob`` connection type: Azure Blob Storage, through adlfs.

Includes ADLS Gen2 accounts. Requires the ``azure`` extra:
``pip install 'dagcraft-pipelines[azure]'``.
"""

import os
import posixpath
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, BinaryIO

import fsspec

from dagcraft.config.connections import AzureBlobConfig
from dagcraft.connections.files.base import FileConnection, FileMode
from dagcraft.connections.files.fsspec_helpers import glob_files, open_binary
from dagcraft.exceptions import ExecutionError
from dagcraft.extras import require_extra
from dagcraft.registry import register_connection

# adlfs checks this variable itself and, when it's set, uses it in place of
# the sign-in we ask for. It isn't a setting of ours: we only look for it so
# an ``account`` connection can't silently sign in as someone else.
ADLFS_CONNECTION_STRING_VARIABLE = "AZURE_STORAGE_CONNECTION_STRING"


@register_connection("azure_blob")
class AzureBlobConnection(FileConnection):
    """Files in an Azure Blob Storage container.

    With ``account``, sign-in uses ``DefaultAzureCredential``: your
    ``az login`` locally, a managed identity in Azure, or service principal
    environment variables. With ``connection_string``, that string is used.
    Step paths are relative to ``prefix`` within the container.
    """

    config_model = AzureBlobConfig
    config: AzureBlobConfig

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        require_extra("adlfs", extra="azure")
        super().__init__(name, config, base_dir)
        self._filesystem: fsspec.AbstractFileSystem | None = None

    def open(self) -> None:
        self._filesystem = self.create_filesystem()

    def close(self) -> None:
        self._filesystem = None

    @property
    def filesystem(self) -> fsspec.AbstractFileSystem:
        """The open filesystem; raises if the connection isn't open."""
        if self._filesystem is None:
            raise self.not_open()
        return self._filesystem

    def create_filesystem(self) -> fsspec.AbstractFileSystem:
        """An adlfs filesystem signed in as the config says."""
        # Imported here so the azure extra is only needed when it's used.
        from adlfs import AzureBlobFileSystem  # noqa: PLC0415

        if self.config.connection_string is not None:
            return AzureBlobFileSystem(
                connection_string=self.config.connection_string.get_secret_value(),
                skip_instance_cache=True,
            )

        account = self.config.account or ""

        if ADLFS_CONNECTION_STRING_VARIABLE in os.environ:
            raise ExecutionError(
                f"Connection '{self.name}' signs in to account '{account}', but "
                f"{ADLFS_CONNECTION_STRING_VARIABLE} is set and adlfs would use "
                "it instead. Unset it, or set 'connection_string' to use a "
                "connection string."
            )

        return AzureBlobFileSystem(
            account_name=account,
            anon=False,
            skip_instance_cache=True,
        )

    def check(self) -> str:
        container = self.config.container

        # Listing really fails on bad credentials or permissions; adlfs's
        # exists() assumes a container exists when it can't tell.
        try:
            self.filesystem.ls(container, detail=False)
        except FileNotFoundError:
            raise ExecutionError(f"Container '{container}' wasn't found.") from None

        prefix = self.config.prefix.strip("/")

        if not prefix:
            return f"container '{container}' is reachable"

        state = "has files" if self.filesystem.exists(self.resolve("")) else "is empty"
        return f"container '{container}' is reachable; prefix '{prefix}' {state}"

    def resolve(self, path: str) -> str:
        """The full path of ``path``: container, then prefix, then path."""
        return posixpath.join(
            self.config.container,
            self.config.prefix.strip("/"),
            path.lstrip("/"),
        )

    def open_file(self, path: str, mode: FileMode) -> AbstractContextManager[BinaryIO]:
        return open_binary(self.filesystem, self.resolve(path), mode)

    def glob(self, pattern: str) -> list[str]:
        return glob_files(self.filesystem, self.resolve(""), self.resolve(pattern))
