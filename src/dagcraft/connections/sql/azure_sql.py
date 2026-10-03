"""The ``azure_sql`` connection type: Azure SQL Database and SQL Server.

Through pyodbc and SQLAlchemy. Requires the ``azure`` extra
(``pip install 'dagcraft-pipelines[azure]'``) and Microsoft's ODBC Driver for
SQL Server installed on the machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from dagcraft.config.connections import AzureSQLConfig
from dagcraft.connections.azure_identity import create_credential
from dagcraft.connections.sql import odbc
from dagcraft.connections.sql.base import POOL_OVERFLOW, SQLConnection
from dagcraft.extras import require_extra
from dagcraft.registry import register_connection

if TYPE_CHECKING:
    import sqlalchemy as sa
    from azure.identity import DefaultAzureCredential

AZURE_SQL_SCOPE = "https://database.windows.net/.default"


@register_connection("azure_sql")
class AzureSQLConnection(SQLConnection):
    """Azure SQL Database or SQL Server.

    With ``server`` and ``database``, sign-in uses an Entra ID token from
    ``DefaultAzureCredential``: your ``az login`` locally, a managed identity
    in Azure. A fresh token is fetched for every new database connection, so
    long runs aren't cut off when a token expires. With
    ``connection_string``, that ODBC connection string is used as it is.

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
        from sqlalchemy import event  # noqa: PLC0415

        if self.config.connection_string is not None:
            return self._engine_for(self.config.connection_string.get_secret_value())

        odbc.check_driver(self.config.driver, self.name)
        self._credential = create_credential()
        engine = self._engine_for(self.odbc_connection_string())
        event.listen(engine, "do_connect", self._provide_token)
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
        """The connection string for signing in to ``server`` and ``database``."""
        return odbc.connection_string(
            self.config.server or "",
            self.config.database or "",
            self.config.driver,
        )

    def _engine_for(self, odbc_connection_string: str) -> sa.Engine:
        import sqlalchemy as sa  # noqa: PLC0415

        url = sa.URL.create(
            "mssql+pyodbc",
            query={"odbc_connect": odbc_connection_string},
        )
        return sa.create_engine(
            url,
            fast_executemany=True,
            pool_pre_ping=True,
            max_overflow=POOL_OVERFLOW,
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
            raise self.not_open()

        token = self._credential.get_token(AZURE_SQL_SCOPE).token
        cparams["attrs_before"] = odbc.token_attribute(token)
