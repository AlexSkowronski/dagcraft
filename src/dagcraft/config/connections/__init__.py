"""The fields of each built-in connection type.

Secrets (connection strings, database URLs) are ``SecretStr``: they never
show in reprs or logs. Keep them out of pipeline files by writing them as
``${env:NAME}``, optionally loaded from the pipeline's ``env_file``.
"""

from dagcraft.config.connections.azure_blob import AzureBlobConfig
from dagcraft.config.connections.azure_sql import AzureSQLConfig
from dagcraft.config.connections.local import LocalConfig
from dagcraft.config.connections.sharepoint import SharePointConfig
from dagcraft.config.connections.sql import SQLConfig

__all__ = [
    "AzureBlobConfig",
    "AzureSQLConfig",
    "LocalConfig",
    "SQLConfig",
    "SharePointConfig",
]
