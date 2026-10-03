import logging
from types import SimpleNamespace
from typing import ClassVar

import fsspec
import pytest
import responses
import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict

from dagcraft import Connection, Pipeline, Reader, register_connection, register_reader
from dagcraft.cli import main
from dagcraft.connections import AzureBlobConnection, AzureSQLConnection

GRAPH = "https://graph.microsoft.com/v1.0"


class ProbeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fail: bool = False


class ProbeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


@register_connection("probe")
class ProbeConnection(Connection):
    """
    Test connection whose check passes or fails on request.
    """

    config_model = ProbeConfig
    events: ClassVar[list[str]] = []

    def open(self) -> None:
        self.events.append(f"open {self.name}")

    def check(self) -> str:
        if self.config.fail:
            raise RuntimeError("access denied")
        return "fine"

    def close(self) -> None:
        self.events.append(f"close {self.name}")


@register_reader(ProbeConnection)
class ProbeReader(Reader):
    options_model = ProbeOptions

    def read(self, connection):
        return None


@pytest.fixture(autouse=True)
def clear_events():
    ProbeConnection.events.clear()


def make_pipeline(tmp_path, *steps, connections):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "connections": connections,
            "steps": list(steps),
        },
        base_dir=tmp_path,
    )


def read(step_id, connection, **fields):
    return {"id": step_id, "type": "read", "connection": connection, **fields}


def summary(checks):
    return [(check.name, check.type, check.ok, check.message) for check in checks]


def test_only_connections_in_use_are_checked_in_order_of_use(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        read("b", "second"),
        read("a", "first"),
        read("again", "second"),
        connections={
            "first": {"type": "probe"},
            "second": {"type": "probe"},
            "unused": {"type": "probe"},
        },
    )

    assert pipeline.connections_in_use() == ["second", "first"]
    assert [check.name for check in pipeline.check_connections()] == [
        "second",
        "first",
    ]
    assert ProbeConnection.events == [
        "open second",
        "close second",
        "open first",
        "close first",
    ]


def test_a_failure_is_reported_and_the_rest_still_checked(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        read("a", "broken"),
        read("b", "fine"),
        connections={
            "broken": {"type": "probe", "fail": True},
            "fine": {"type": "probe"},
        },
    )

    assert summary(pipeline.check_connections()) == [
        ("broken", "probe", False, "access denied"),
        ("fine", "probe", True, "fine"),
    ]
    assert "close broken" in ProbeConnection.events


def test_local_folders(tmp_path):
    (tmp_path / "data").mkdir()
    pipeline = make_pipeline(
        tmp_path,
        read("a", "data", path="in.csv"),
        {
            "id": "b",
            "type": "write",
            "connection": "out",
            "path": "x.csv",
            "inputs": {"data": "a"},
        },
        connections={
            "data": {"type": "local", "root": "data"},
            "out": {"type": "local", "root": "not_yet"},
        },
    )

    data, out = pipeline.check_connections()

    assert data.ok
    assert data.message == f"{tmp_path / 'data'} is reachable"
    assert out.ok
    assert out.message.endswith("doesn't exist yet; writing will create it")


def test_sql(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        read("a", "db", table="t"),
        read("b", "nowhere", table="t"),
        connections={
            "db": {"type": "sql", "url": "sqlite:///warehouse.db"},
            "nowhere": {"type": "sql", "url": "nosuchdb://server/db"},
        },
    )

    db, nowhere = pipeline.check_connections()

    assert (db.ok, db.message) == (True, "connected")
    assert not nowhere.ok
    assert "nosuchdb" in nowhere.message


def test_azure_sql_reports_who_it_connected_as(tmp_path, monkeypatch):
    monkeypatch.setattr(
        AzureSQLConnection,
        "_engine_for",
        lambda _self, _odbc: sa.create_engine("sqlite://"),
    )
    monkeypatch.setattr(
        AzureSQLConnection,
        "check_query",
        "SELECT 'me@contoso.com', 'analytics'",
    )
    pipeline = make_pipeline(
        tmp_path,
        read("a", "warehouse", table="t"),
        connections={
            "warehouse": {
                "type": "azure_sql",
                "connection_string": "Driver={x};Server=y;",
            }
        },
    )

    [check] = pipeline.check_connections()

    assert (check.ok, check.message) == (
        True,
        "connected to analytics as me@contoso.com",
    )


@pytest.fixture
def memory_container(monkeypatch):
    filesystem = fsspec.filesystem("memory", skip_instance_cache=True)
    filesystem.store.clear()
    monkeypatch.setattr(
        AzureBlobConnection, "create_filesystem", lambda _self: filesystem
    )
    yield filesystem
    filesystem.store.clear()
    filesystem.pseudo_dirs[:] = [""]


def test_azure_blob(tmp_path, memory_container):
    memory_container.pipe("raw/events/a.json", b"[]")
    blob = {"type": "azure_blob", "account": "acct"}
    pipeline = make_pipeline(
        tmp_path,
        read("a", "events", path="x.json"),
        read("b", "empty", path="x.json"),
        read("c", "missing", path="x.json"),
        connections={
            "events": {**blob, "container": "raw", "prefix": "events"},
            "empty": {**blob, "container": "raw", "prefix": "nothing_here"},
            "missing": {**blob, "container": "nope"},
        },
    )

    assert summary(pipeline.check_connections()) == [
        (
            "events",
            "azure_blob",
            True,
            "container 'raw' is reachable; prefix 'events' has files",
        ),
        (
            "empty",
            "azure_blob",
            True,
            "container 'raw' is reachable; prefix 'nothing_here' is empty",
        ),
        ("missing", "azure_blob", False, "Container 'nope' wasn't found."),
    ]


@pytest.fixture
def fake_credential(monkeypatch):
    credential = SimpleNamespace(
        get_token=lambda *_scopes: SimpleNamespace(token="abc"),
        close=lambda: None,
    )
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)


@pytest.mark.usefixtures("fake_credential")
def test_sharepoint(tmp_path):
    site = f"{GRAPH}/sites/contoso.sharepoint.com:/sites/Finance"
    drives = {"value": [{"id": "d1", "name": "Documents"}]}
    sharepoint = {"type": "sharepoint", "site": "contoso.sharepoint.com/sites/Finance"}

    with responses.RequestsMock() as graph:
        for _ in range(2):
            graph.get(site, json={"id": "s1"})
            graph.get(f"{GRAPH}/sites/s1/drives", json=drives)
        graph.get(f"{GRAPH}/drives/d1/root:/Reports:/children", json={"value": []})
        graph.get(f"{GRAPH}/drives/d1/root:/Later:/children", status=404, json={})

        pipeline = make_pipeline(
            tmp_path,
            read("a", "reports", path="x.csv"),
            read("b", "later", path="x.csv"),
            connections={
                "reports": {**sharepoint, "folder": "Reports"},
                "later": {**sharepoint, "folder": "Later"},
            },
        )
        checks = summary(pipeline.check_connections())

    library = "library 'Documents' on contoso.sharepoint.com/sites/Finance"
    assert checks == [
        (
            "reports",
            "sharepoint",
            True,
            f"{library} is reachable; folder 'Reports' found",
        ),
        (
            "later",
            "sharepoint",
            True,
            f"{library} is reachable; folder 'Later' doesn't exist yet",
        ),
    ]


@pytest.mark.usefixtures("fake_credential")
def test_sharepoint_access_denied(tmp_path):
    with responses.RequestsMock() as graph:
        graph.get(
            f"{GRAPH}/sites/contoso.sharepoint.com:/sites/Finance",
            status=403,
            json={"error": {"message": "Access denied."}},
        )
        pipeline = make_pipeline(
            tmp_path,
            read("a", "sp", path="x.csv"),
            connections={
                "sp": {
                    "type": "sharepoint",
                    "site": "contoso.sharepoint.com/sites/Finance",
                }
            },
        )
        [check] = pipeline.check_connections()

    assert not check.ok
    assert "SharePoint returned 403" in check.message
    assert "Access denied." in check.message


def write_pipeline(tmp_path, connections):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        f"""
pipeline:
  name: cli
connections:
{connections}
steps:
  - id: a
    type: read
    connection: first
  - id: b
    type: read
    connection: second
""",
        encoding="utf-8",
    )
    return path


def cli_lines(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "dagcraft.cli.report"
    ]


def test_cli_check_connections(tmp_path, caplog):
    path = write_pipeline(
        tmp_path,
        "  first: {type: probe}\n  second: {type: probe}",
    )

    with caplog.at_level(logging.INFO):
        assert main([str(path), "--check-connections"]) == 0

    assert cli_lines(caplog) == [
        "Pipeline 'cli' is valid.",
        "Checking 2 connection(s):",
        "  first   probe  OK      fine",
        "  second  probe  OK      fine",
        "All connections work.",
    ]


def test_cli_check_connections_failure_exits_nonzero(tmp_path, caplog):
    path = write_pipeline(
        tmp_path,
        "  first: {type: probe}\n  second: {type: probe, fail: true}",
    )

    with caplog.at_level(logging.INFO):
        assert main([str(path), "--check-connections", "--dry-run"]) == 1

    lines = cli_lines(caplog)
    assert lines[0] == "Pipeline 'cli' is valid."
    assert "Steps, in run order:" in lines
    assert "  second  probe  FAILED  access denied" in lines
    assert lines[-1] == "1 of 2 connection(s) failed."
