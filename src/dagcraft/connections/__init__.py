"""
Connections: where data lives and how to sign in to it.

Importing this package registers the built-in connection types::

    Connection (base.py)          open / close / check
    ├── FileConnection (files/)   open_file / glob
    │   ├── local
    │   ├── azure_blob
    │   └── sharepoint
    └── SQLConnection (sql/)      a SQLAlchemy engine
        ├── sql                   any database, by URL
        └── azure_sql
"""

from dagcraft.connections.base import Connection
from dagcraft.connections.files import (
    AzureBlobConnection,
    FileConnection,
    LocalConnection,
    SharePointConnection,
)
from dagcraft.connections.sql import (
    AzureSQLConnection,
    GenericSQLConnection,
    SQLConnection,
)

__all__ = [
    "AzureBlobConnection",
    "AzureSQLConnection",
    "Connection",
    "FileConnection",
    "GenericSQLConnection",
    "LocalConnection",
    "SQLConnection",
    "SharePointConnection",
]
