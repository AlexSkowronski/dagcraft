"""Connection types. Importing this package registers the built-in ones."""

from dagcraft.connections.azure_blob import AzureBlobConfig, AzureBlobConnection
from dagcraft.connections.azure_sql import AzureSQLConfig, AzureSQLConnection
from dagcraft.connections.base import Connection
from dagcraft.connections.files import FileConnection, FileOptions
from dagcraft.connections.local import LocalConfig, LocalConnection
from dagcraft.connections.sql import (
    GenericSQLConnection,
    SQLConfig,
    SQLConnection,
    SQLReadOptions,
    SQLWriteOptions,
)

__all__ = [
    "AzureBlobConfig",
    "AzureBlobConnection",
    "AzureSQLConfig",
    "AzureSQLConnection",
    "Connection",
    "FileConnection",
    "FileOptions",
    "GenericSQLConnection",
    "LocalConfig",
    "LocalConnection",
    "SQLConfig",
    "SQLConnection",
    "SQLReadOptions",
    "SQLWriteOptions",
]
