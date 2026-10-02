"""Azure Blob Storage, including ADLS Gen2 accounts, via adlfs.

Requires the ``azure`` extra: ``pip install 'dagcraft[azure]'``.
"""

from __future__ import annotations

import importlib.util
import os
import posixpath
from pathlib import Path
from typing import Any, Self

import fsspec
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.connections.files import FileConnection
from dagcraft.exceptions import ConfigError, ExecutionError
from dagcraft.registry import register_connection

# adlfs reads this itself and prefers it over every other kind of sign-in.
CONNECTION_STRING_VARIABLE = "AZURE_STORAGE_CONNECTION_STRING"


class AzureBlobConfig(BaseModel):
    """Set exactly one of ``account`` or ``connection_string_env``."""

    model_config = ConfigDict(extra="forbid")

    container: str = Field(min_length=1)
    prefix: str = ""
    account: str | None = Field(default=None, min_length=1)
    connection_string_env: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def check_auth(self) -> Self:
        if (self.account is None) == (self.connection_string_env is None):
            raise ValueError(
                "Set exactly one of 'account' (sign in with "
                "DefaultAzureCredential) or 'connection_string_env'."
            )
        return self


@register_connection("azure_blob")
class AzureBlobConnection(FileConnection):
    """Files in an Azure Blob Storage container.

    With ``account``, sign-in uses ``DefaultAzureCredential``: an Azure CLI
    login locally, managed identity in Azure, or service principal
    environment variables. With ``connection_string_env``, the connection
    string is read from that environment variable when the connection opens.

    Step paths are relative to ``prefix`` within the container.
    """

    config_model = AzureBlobConfig
    config: AzureBlobConfig

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        if not adlfs_installed():
            raise ConfigError(
                "this connection type needs the 'azure' extra. "
                "Install it with: pip install 'dagcraft[azure]'"
            )
        super().__init__(name, config, base_dir)

    def create_filesystem(self) -> fsspec.AbstractFileSystem:
        # Imported here so the azure extra is only needed when it's used.
        from adlfs import AzureBlobFileSystem  # noqa: PLC0415

        variable = self.config.connection_string_env

        if variable is not None:
            return AzureBlobFileSystem(
                connection_string=self._read_variable(variable),
                skip_instance_cache=True,
            )

        if CONNECTION_STRING_VARIABLE in os.environ:
            raise ExecutionError(
                f"Connection '{self.name}' signs in to account "
                f"'{self.config.account}', but {CONNECTION_STRING_VARIABLE} is "
                "set and adlfs would use it instead. Unset it, or use "
                "'connection_string_env' to choose a connection string."
            )

        return AzureBlobFileSystem(
            account_name=self.config.account,
            anon=False,
            skip_instance_cache=True,
        )

    def resolve(self, path: str) -> str:
        return posixpath.join(
            self.config.container,
            self.config.prefix.strip("/"),
            path.lstrip("/"),
        )

    def _read_variable(self, variable: str) -> str:
        value = os.environ.get(variable)

        if not value:
            raise ExecutionError(
                f"Connection '{self.name}' reads its connection string from "
                f"the environment variable '{variable}', which is not set."
            )
        return value


def adlfs_installed() -> bool:
    return importlib.util.find_spec("adlfs") is not None
