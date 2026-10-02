import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pyodbc
import pytest
import sqlalchemy as sa

from dagcraft import ConfigError, Pipeline, extras
from dagcraft.connections.azure_sql import (
    AZURE_SQL_SCOPE,
    SQL_COPT_SS_ACCESS_TOKEN,
    AzureSQLConfig,
    AzureSQLConnection,
)
from dagcraft.exceptions import ExecutionError

DRIVER = "ODBC Driver 18 for SQL Server"


class FakeCredential:
    """Stands in for DefaultAzureCredential; hands out a fixed token."""

    instances: ClassVar[list["FakeCredential"]] = []

    def __init__(self):
        self.requested_scopes = []
        self.closed = False
        FakeCredential.instances.append(self)

    def get_token(self, *scopes):
        self.requested_scopes.extend(scopes)
        return SimpleNamespace(token="abc")

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_azure(monkeypatch):
    FakeCredential.instances.clear()
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(pyodbc, "drivers", lambda: [DRIVER])


def make_connection(**config):
    return AzureSQLConnection("warehouse", AzureSQLConfig(**config), Path())


def signed_in(**extra):
    return make_connection(
        server="myserver.database.windows.net",
        database="analytics",
        **extra,
    )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (
            {},
            "Set 'server' and 'database' (sign in with DefaultAzureCredential) "
            "or 'connection_string_env', but not both.",
        ),
        (
            {"server": "s", "database": "d", "connection_string_env": "X"},
            "but not both",
        ),
        (
            {"server": "s"},
            "Set both 'server' and 'database'.",
        ),
    ],
)
def test_config_validation(config, message):
    with pytest.raises(ConfigError) as exc_info:
        Pipeline.from_dict(
            {
                "pipeline": {"name": "test"},
                "connections": {"warehouse": {"type": "azure_sql", **config}},
                "steps": [],
            }
        )

    assert message in str(exc_info.value)


def test_missing_extra_is_a_config_error(monkeypatch):
    monkeypatch.setattr(extras, "module_available", lambda _module: False)

    with pytest.raises(ConfigError, match=r"pip install 'dagcraft\[azure\]'"):
        signed_in()


@pytest.mark.parametrize(
    ("server", "expected"),
    [
        ("myserver.database.windows.net", "myserver.database.windows.net,1433"),
        ("myserver.database.windows.net,14330", "myserver.database.windows.net,14330"),
    ],
)
def test_odbc_connection_string(server, expected):
    connection = make_connection(server=server, database="analytics")

    assert connection.odbc_connection_string() == (
        f"Driver={{{DRIVER}}};Server=tcp:{expected};Database=analytics;"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


def test_sign_in_passes_a_fresh_token_to_each_connection():
    connection = signed_in()
    connection.open()

    try:
        engine = connection.engine
        assert engine.url.query["odbc_connect"] == connection.odbc_connection_string()
        assert engine.dialect.fast_executemany is True
        assert sa.event.contains(engine, "do_connect", connection._provide_token)

        # Simulate SQLAlchemy opening two database connections.
        first: dict[str, Any] = {}
        second: dict[str, Any] = {}
        connection._provide_token(None, None, [], first)
        connection._provide_token(None, None, [], second)

        token = "abc".encode("utf-16-le")
        expected = struct.pack(f"<I{len(token)}s", len(token), token)
        assert first["attrs_before"] == {SQL_COPT_SS_ACCESS_TOKEN: expected}

        [credential] = FakeCredential.instances
        assert credential.requested_scopes == [AZURE_SQL_SCOPE, AZURE_SQL_SCOPE]
    finally:
        connection.close()

    assert credential.closed
    with pytest.raises(ExecutionError, match="is not open"):
        _ = connection.engine


def test_connection_string_comes_from_the_environment(monkeypatch):
    odbc = "Driver={Some Driver};Server=tcp:example,1433;Uid=user;Pwd=secret;"
    monkeypatch.setenv("WAREHOUSE_ODBC", odbc)
    # The driver named in the connection string isn't checked.
    monkeypatch.setattr(pyodbc, "drivers", list)

    connection = make_connection(connection_string_env="WAREHOUSE_ODBC")
    connection.open()

    try:
        assert connection.engine.url.query["odbc_connect"] == odbc
        assert not sa.event.contains(
            connection.engine, "do_connect", connection._provide_token
        )
        assert FakeCredential.instances == []
    finally:
        connection.close()


def test_missing_connection_string_variable_fails_on_open():
    connection = make_connection(connection_string_env="WAREHOUSE_ODBC")

    with pytest.raises(ExecutionError, match="'WAREHOUSE_ODBC', which is not set"):
        connection.open()


def test_missing_driver_fails_on_open(monkeypatch):
    monkeypatch.setattr(pyodbc, "drivers", lambda: ["SQL Server"])
    connection = signed_in()

    with pytest.raises(ExecutionError) as exc_info:
        connection.open()

    message = str(exc_info.value)
    assert f"needs the ODBC driver '{DRIVER}'" in message
    assert "installed: SQL Server" in message
    assert FakeCredential.instances == []
