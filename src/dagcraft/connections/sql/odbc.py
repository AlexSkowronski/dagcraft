"""ODBC details for SQL Server: connection strings, drivers, access tokens."""

import struct

from dagcraft.exceptions import ExecutionError

# pyodbc connection attribute that carries an Entra ID access token.
SQL_COPT_SS_ACCESS_TOKEN = 1256
DEFAULT_PORT = 1433
DRIVER_DOWNLOAD_URL = (
    "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
)


def connection_string(server: str, database: str, driver: str) -> str:
    """An encrypted ODBC connection string, without credentials.

    The server's port defaults to 1433 unless given as ``server,port``.
    """
    if "," not in server:
        server = f"{server},{DEFAULT_PORT}"

    return (
        f"Driver={{{driver}}};"
        f"Server=tcp:{server};"
        f"Database={database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


def check_driver(driver: str, connection: str) -> None:
    """Raise ``ExecutionError``, saying where to get it, if ``driver`` is missing."""
    import pyodbc  # noqa: PLC0415 - from the azure extra, needed only here

    installed = pyodbc.drivers()

    if driver not in installed:
        raise ExecutionError(
            f"Connection '{connection}' needs the ODBC driver '{driver}', which "
            f"isn't installed (installed: {', '.join(installed) or 'none'}). "
            f"Download it from {DRIVER_DOWNLOAD_URL}"
        )


def token_attribute(token: str) -> dict[int, bytes]:
    """The pyodbc ``attrs_before`` setting that signs in with an access token.

    The driver expects the token as UTF-16-LE bytes, prefixed by their length.
    """
    encoded = token.encode("utf-16-le")
    return {
        SQL_COPT_SS_ACCESS_TOKEN: struct.pack(
            f"<I{len(encoded)}s",
            len(encoded),
            encoded,
        ),
    }
