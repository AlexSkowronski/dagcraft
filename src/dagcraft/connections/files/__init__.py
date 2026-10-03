"""Connections to storage that holds files. Importing registers the built-in ones."""

from dagcraft.connections.files.azure_blob import AzureBlobConnection
from dagcraft.connections.files.base import FileConnection, FileMode
from dagcraft.connections.files.local import LocalConnection
from dagcraft.connections.files.sharepoint import SharePointConnection

__all__ = [
    "AzureBlobConnection",
    "FileConnection",
    "FileMode",
    "LocalConnection",
    "SharePointConnection",
]
