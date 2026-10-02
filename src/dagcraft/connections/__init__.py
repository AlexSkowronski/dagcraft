"""Connection types. Importing this package registers the built-in ones."""

from dagcraft.connections.azure_blob import AzureBlobConfig, AzureBlobConnection
from dagcraft.connections.base import Connection
from dagcraft.connections.files import FileConnection, FileOptions
from dagcraft.connections.local import LocalConfig, LocalConnection

__all__ = [
    "AzureBlobConfig",
    "AzureBlobConnection",
    "Connection",
    "FileConnection",
    "FileOptions",
    "LocalConfig",
    "LocalConnection",
]
