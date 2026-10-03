"""
Connections to SQL databases. Importing registers the built-in ones.
"""

from dagcraft.connections.sql.azure_sql import AzureSQLConnection
from dagcraft.connections.sql.base import SQLConnection
from dagcraft.connections.sql.generic import GenericSQLConnection

__all__ = [
    "AzureSQLConnection",
    "GenericSQLConnection",
    "SQLConnection",
]
