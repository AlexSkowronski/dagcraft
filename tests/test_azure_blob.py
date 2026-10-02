from pathlib import Path

import fsspec
import pandas as pd
import pytest
from adlfs import AzureBlobFileSystem
from azure.identity.aio import DefaultAzureCredential

from dagcraft import ConfigError, Pipeline, PipelineError
from dagcraft.connections import azure_blob
from dagcraft.connections.azure_blob import AzureBlobConfig, AzureBlobConnection
from dagcraft.exceptions import ExecutionError

# Variables adlfs reads on its own; cleared so the machine running the tests
# can't change which kind of sign-in is used.
ADLFS_VARIABLES = [
    "AZURE_STORAGE_ACCOUNT_NAME",
    "AZURE_STORAGE_ACCOUNT_KEY",
    "AZURE_STORAGE_ANON",
    "AZURE_STORAGE_CLIENT_ID",
    "AZURE_STORAGE_CLIENT_SECRET",
    "AZURE_STORAGE_CONNECTION_STRING",
    "AZURE_STORAGE_SAS_TOKEN",
    "AZURE_STORAGE_TENANT_ID",
]

# Points at a local emulator address; never used to connect.
FAKE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=ZmFrZQ==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for variable in ADLFS_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def memory_filesystem(monkeypatch):
    """Stand in for the container with fsspec's in-memory filesystem."""
    filesystem = fsspec.filesystem("memory", skip_instance_cache=True)
    filesystem.store.clear()
    monkeypatch.setattr(
        AzureBlobConnection,
        "create_filesystem",
        lambda _self: filesystem,
    )
    yield filesystem
    filesystem.store.clear()
    filesystem.pseudo_dirs[:] = [""]


def make_connection(**config):
    return AzureBlobConnection("lake", AzureBlobConfig(**config), Path())


def make_pipeline(*steps, lake):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "connections": {"lake": {"type": "azure_blob", **lake}},
            "steps": list(steps),
        }
    )


@pytest.mark.parametrize(
    ("lake", "message"),
    [
        (
            {"container": "raw"},
            "Set exactly one of 'account'",
        ),
        (
            {"container": "raw", "account": "acct", "connection_string_env": "X"},
            "Set exactly one of 'account'",
        ),
        (
            {"account": "acct"},
            "container: Field required",
        ),
        (
            {"container": "raw", "account": "acct", "key": "secret"},
            "key: Extra inputs are not permitted",
        ),
    ],
)
def test_config_validation(lake, message):
    with pytest.raises(ConfigError) as exc_info:
        make_pipeline(lake=lake)

    assert message in str(exc_info.value)


def test_missing_extra_is_a_config_error(monkeypatch):
    monkeypatch.setattr(azure_blob, "adlfs_installed", lambda: False)

    with pytest.raises(ConfigError) as exc_info:
        make_pipeline(lake={"container": "raw", "account": "acct"})

    assert "Connection 'lake'" in str(exc_info.value)
    assert "pip install 'dagcraft[azure]'" in str(exc_info.value)


@pytest.mark.parametrize(
    ("prefix", "path", "expected"),
    [
        ("", "orders.csv", "raw/orders.csv"),
        ("sales/2026", "orders.csv", "raw/sales/2026/orders.csv"),
        ("/sales/", "/daily/orders.csv", "raw/sales/daily/orders.csv"),
    ],
)
def test_paths_resolve_inside_the_container(prefix, path, expected):
    connection = make_connection(container="raw", prefix=prefix, account="acct")

    assert connection.resolve(path) == expected


def test_account_signs_in_with_default_credential():
    connection = make_connection(container="raw", account="acct")
    connection.open()

    try:
        filesystem = connection.filesystem
        assert isinstance(filesystem, AzureBlobFileSystem)
        assert filesystem.account_name == "acct"
        assert isinstance(filesystem.credential, DefaultAzureCredential)
    finally:
        connection.close()


def test_connection_string_is_read_from_the_named_variable(monkeypatch):
    monkeypatch.setenv("LAKE_CONNECTION", FAKE_CONNECTION_STRING)
    connection = make_connection(
        container="raw",
        connection_string_env="LAKE_CONNECTION",
    )
    connection.open()

    try:
        assert connection.filesystem.connection_string == FAKE_CONNECTION_STRING
    finally:
        connection.close()


def test_missing_connection_string_variable_fails_the_step():
    pipeline = make_pipeline(
        {"id": "load", "type": "read", "connection": "lake", "path": "x.csv"},
        lake={"container": "raw", "connection_string_env": "LAKE_CONNECTION"},
    )

    with pytest.raises(PipelineError) as exc_info:
        pipeline.run()

    assert "failed at step 'load'" in str(exc_info.value)
    assert "'LAKE_CONNECTION', which is not set" in str(exc_info.value)


@pytest.mark.parametrize("value", [FAKE_CONNECTION_STRING, ""])
def test_ambient_connection_string_is_refused(monkeypatch, value):
    # adlfs would silently use it instead of signing in, even when empty.
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", value)
    connection = make_connection(container="raw", account="acct")

    with pytest.raises(ExecutionError, match="adlfs would use it instead"):
        connection.open()


def test_write_and_read_through_the_container(tmp_path, memory_filesystem):
    pd.DataFrame({"value": [1, 2]}).to_csv(tmp_path / "in.csv", index=False)
    lake = {"container": "raw", "prefix": "sales", "account": "acct"}

    upload = make_pipeline(
        {"id": "source", "type": "read", "path": str(tmp_path / "in.csv")},
        {
            "id": "save",
            "type": "write",
            "connection": "lake",
            "path": "daily/out.parquet",
            "inputs": {"data": "source"},
        },
        lake=lake,
    )
    upload.run()

    assert memory_filesystem.exists("raw/sales/daily/out.parquet")

    download = make_pipeline(
        {
            "id": "load",
            "type": "read",
            "connection": "lake",
            "path": "daily/out.parquet",
        },
        lake=lake,
    )

    assert download.run().artifact("load")["value"].tolist() == [1, 2]
