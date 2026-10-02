"""Azure SQL Database and SQL Server, through pyodbc and SQLAlchemy.

Requires the ``azure`` extra (``pip install 'dagcraft-pipelines[azure]'``) and
Microsoft's ODBC Driver for SQL Server installed on the machine.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.connections.base import read_variable
from dagcraft.connections.sql import SQLConnection
from dagcraft.exceptions import ExecutionError
from dagcraft.extras import require_extra
from dagcraft.registry import register_connection

if TYPE_CHECKING:
    import sqlalchemy as sa
    from azure.identity import DefaultAzureCredential

# pyodbc connection attribute that carries an Entra ID access token.
SQL_COPT_SS_ACCESS_TOKEN = 1256
AZURE_SQL_SCOPE = "https://database.windows.net/.default"
DRIVER_DOWNLOAD_URL = (
    "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
)


class AzureSQLConfig(BaseModel):
    """Set ``server`` and ``database``, or ``connection_string_env``."""

    model_config = ConfigDict(extra="forbid")

    server: str | None = Field(default=None, min_length=1)
    database: str | None = Field(default=None, min_length=1)
    driver: str = Field(default="ODBC Driver 18 for SQL Server", min_length=1)
    connection_string_env: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def check_auth(self) -> Self:
        signs_in = self.server is not None or self.database is not None

        if signs_in == (self.connection_string_env is not None):
            raise ValueError(
                "Set 'server' and 'database' (sign in with "
                "DefaultAzureCredential) or 'connection_string_env', but not both."
            )

        if signs_in and (self.server is None or self.database is None):
            raise ValueError("Set both 'server' and 'database'.")
        return self


@register_connection("azure_sql")
class AzureSQLConnection(SQLConnection):
    """Azure SQL Database or SQL Server.

    With ``server`` and ``database``, sign-in uses an Entra ID token from
    ``DefaultAzureCredential``: an Azure CLI login locally, managed identity
    in Azure. A fresh token is fetched for every new database connection, so
    long runs aren't cut off when a token expires. With
    ``connection_string_env``, an ODBC connection string (for example one
    using SQL authentication) is read from that environment variable.

    Writes use pyodbc's ``fast_executemany``.
    """

    config_model = AzureSQLConfig
    config: AzureSQLConfig
    extra = "azure"
    check_query = "SELECT SUSER_SNAME(), DB_NAME()"

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        require_extra("pyodbc", "azure.identity", extra=self.extra)
        super().__init__(name, config, base_dir)
        self._credential: DefaultAzureCredential | None = None

    def create_engine(self) -> sa.Engine:
        import sqlalchemy as sa  # noqa: PLC0415
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        variable = self.config.connection_string_env

        if variable is not None:
            return self._engine_for(
                read_variable(variable, self.name, "connection string")
            )

        self._check_driver()

        self._credential = DefaultAzureCredential()
        engine = self._engine_for(self.odbc_connection_string())
        sa.event.listen(engine, "do_connect", self._provide_token)
        return engine

    def close(self) -> None:
        super().close()

        if self._credential is not None:
            self._credential.close()
            self._credential = None

    def check(self) -> str:
        import sqlalchemy as sa  # noqa: PLC0415

        # Report who we signed in as: DefaultAzureCredential may not pick
        # the identity you expect.
        with self.engine.connect() as connection:
            login, database = connection.execute(sa.text(self.check_query)).one()

        return f"connected to {database} as {login}"

    def odbc_connection_string(self) -> str:
        server = self.config.server or ""

        if "," not in server:
            server = f"{server},1433"

        return (
            f"Driver={{{self.config.driver}}};"
            f"Server=tcp:{server};"
            f"Database={self.config.database};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )

    def _engine_for(self, odbc_connection_string: str) -> sa.Engine:
        import sqlalchemy as sa  # noqa: PLC0415

        url = sa.URL.create(
            "mssql+pyodbc",
            query={"odbc_connect": odbc_connection_string},
        )
        return sa.create_engine(url, fast_executemany=True, pool_pre_ping=True)

    def _check_driver(self) -> None:
        import pyodbc  # noqa: PLC0415

        installed = pyodbc.drivers()

        if self.config.driver not in installed:
            raise ExecutionError(
                f"Connection '{self.name}' needs the ODBC driver "
                f"'{self.config.driver}', which isn't installed (installed: "
                f"{', '.join(installed) or 'none'}). Download it from "
                f"{DRIVER_DOWNLOAD_URL}"
            )

    def _provide_token(
        self,
        dialect: Any,
        connection_record: Any,
        cargs: list[Any],
        cparams: dict[str, Any],
    ) -> None:
        """Pass a fresh access token to each new database connection."""
        if self._credential is None:
            raise ExecutionError(f"Connection '{self.name}' is not open.")

        token = self._credential.get_token(AZURE_SQL_SCOPE).token.encode("utf-16-le")
        cparams["attrs_before"] = {
            SQL_COPT_SS_ACCESS_TOKEN: struct.pack(
                f"<I{len(token)}s",
                len(token),
                token,
            ),
        }
