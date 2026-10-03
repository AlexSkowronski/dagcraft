"""The ``azure_sql`` connection type."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class AzureSQLConfig(BaseModel):
    """An Azure SQL database or SQL Server.

    Set ``server`` and ``database`` to sign in as yourself (``az login``), a
    managed identity or a service principal, through
    ``DefaultAzureCredential``; or set ``connection_string`` to a full ODBC
    connection string (for example with SQL authentication), usually as
    ``${env:NAME}``.
    """

    model_config = ConfigDict(extra="forbid")

    server: str | None = Field(default=None, min_length=1)
    database: str | None = Field(default=None, min_length=1)
    driver: str = Field(default="ODBC Driver 18 for SQL Server", min_length=1)
    connection_string: SecretStr | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def check_sign_in(self) -> Self:
        """Either a server and database to sign in to, or a connection string."""
        signs_in = self.server is not None or self.database is not None

        if signs_in == (self.connection_string is not None):
            raise ValueError(
                "Set 'server' and 'database' (sign in with "
                "DefaultAzureCredential) or 'connection_string', but not both."
            )

        if signs_in and (self.server is None or self.database is None):
            raise ValueError("Set both 'server' and 'database'.")
        return self
