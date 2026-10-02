import io
from types import SimpleNamespace
from typing import ClassVar

import pandas as pd
import pytest
import responses

from dagcraft import ConfigError, Pipeline, PipelineError, extras

GRAPH = "https://graph.microsoft.com/v1.0"
SITE = f"{GRAPH}/sites/contoso.sharepoint.com:/sites/Finance"
DRIVE = f"{GRAPH}/drives/drive-1"


class FakeCredential:
    instances: ClassVar[list["FakeCredential"]] = []

    def __init__(self):
        self.closed = False
        FakeCredential.instances.append(self)

    def get_token(self, *_scopes):
        return SimpleNamespace(token="abc")

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_credential(monkeypatch):
    FakeCredential.instances.clear()
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", FakeCredential)


@pytest.fixture
def graph():
    with responses.RequestsMock() as mock:
        mock.get(SITE, json={"id": "site-1"})
        mock.get(
            f"{GRAPH}/sites/site-1/drives",
            json={
                "value": [
                    {"id": "drive-0", "name": "Site Assets"},
                    {"id": "drive-1", "name": "Documents"},
                ]
            },
        )
        yield mock


def make_pipeline(tmp_path, *steps, **sharepoint):
    config = {"site": "contoso.sharepoint.com/sites/Finance", **sharepoint}
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "connections": {"sp": {"type": "sharepoint", **config}},
            "steps": list(steps),
        },
        base_dir=tmp_path,
    )


def csv_bytes(**columns):
    return pd.DataFrame(columns).to_csv(index=False).encode()


def test_reads_a_file(tmp_path, graph):
    graph.get(
        f"{DRIVE}/root:/Reports/2026/Q1%20sales.csv:/content",
        body=csv_bytes(region=["North"], revenue=[10]),
    )

    result = make_pipeline(
        tmp_path,
        {"id": "sales", "type": "read", "connection": "sp", "path": "Q1 sales.csv"},
        folder="Reports/2026",
    ).run()

    assert result.artifact("sales").to_dict("list") == {
        "region": ["North"],
        "revenue": [10],
    }
    assert all(
        call.request.headers["Authorization"] == "Bearer abc" for call in graph.calls
    )
    [credential] = FakeCredential.instances
    assert credential.closed


def test_writes_a_file(tmp_path, graph):
    pd.DataFrame({"a": [1, 2]}).to_csv(tmp_path / "in.csv", index=False)
    graph.put(f"{DRIVE}/root:/Exports/out.csv:/content", json={"id": "item"})

    make_pipeline(
        tmp_path,
        {"id": "data", "type": "read", "path": "in.csv"},
        {
            "id": "upload",
            "type": "write",
            "connection": "sp",
            "path": "Exports/out.csv",
            "inputs": {"data": "data"},
        },
    ).run()

    upload = graph.calls[-1].request
    assert upload.method == "PUT"
    assert upload.headers["Content-Type"] == "application/octet-stream"
    assert pd.read_csv(io.BytesIO(upload.body))["a"].tolist() == [1, 2]


def test_wildcards_list_the_folder_across_pages(tmp_path, graph):
    children = f"{DRIVE}/root:/Inbox/daily:/children"
    graph.get(
        children,
        json={
            "value": [
                {"name": "2026-10-01.csv", "file": {}},
                {"name": "archive", "folder": {}},
                {"name": "readme.txt", "file": {}},
            ],
            "@odata.nextLink": f"{children}?$skiptoken=page2",
        },
    )
    graph.get(children, json={"value": [{"name": "2026-10-02.csv", "file": {}}]})
    for day, value in [("01", 1), ("02", 2)]:
        graph.get(
            f"{DRIVE}/root:/Inbox/daily/2026-10-{day}.csv:/content",
            body=csv_bytes(n=[value]),
        )

    frame = (
        make_pipeline(
            tmp_path,
            {
                "id": "daily",
                "type": "read",
                "connection": "sp",
                "path": "daily/*.csv",
                "source_column": "file",
            },
            folder="Inbox",
        )
        .run()
        .artifact("daily")
    )

    assert frame.to_dict("list") == {
        "n": [1, 2],
        "file": ["daily/2026-10-01.csv", "daily/2026-10-02.csv"],
    }


@pytest.mark.usefixtures("graph")
def test_wildcards_in_folder_names_are_rejected(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        {"id": "daily", "type": "read", "connection": "sp", "path": "*/x.csv"},
    )

    with pytest.raises(PipelineError, match="only use wildcards in the file name"):
        pipeline.run()


@pytest.mark.usefixtures("graph")
def test_unknown_library_lists_the_available_ones(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        {"id": "x", "type": "read", "connection": "sp", "path": "x.csv"},
        library="Reports",
    )

    with pytest.raises(PipelineError) as exc_info:
        pipeline.run()

    assert "no document library named 'Reports'" in str(exc_info.value)
    assert "Available: Site Assets, Documents." in str(exc_info.value)


def test_missing_file_reports_graphs_message(tmp_path, graph):
    graph.get(
        f"{DRIVE}/root:/missing.csv:/content",
        status=404,
        json={
            "error": {
                "code": "itemNotFound",
                "message": "The resource could not be found.",
            }
        },
    )
    pipeline = make_pipeline(
        tmp_path,
        {"id": "x", "type": "read", "connection": "sp", "path": "missing.csv"},
    )

    with pytest.raises(PipelineError) as exc_info:
        pipeline.run()

    assert "SharePoint returned 404" in str(exc_info.value)
    assert "The resource could not be found." in str(exc_info.value)


@pytest.mark.parametrize(
    ("site", "site_url"),
    [
        ("https://contoso.sharepoint.com/sites/Finance/", SITE),
        ("contoso.sharepoint.com", f"{GRAPH}/sites/contoso.sharepoint.com"),
    ],
)
def test_site_address(tmp_path, site, site_url):
    with responses.RequestsMock() as graph:
        graph.get(site_url, json={"id": "site-1"})
        graph.get(
            f"{GRAPH}/sites/site-1/drives",
            json={"value": [{"id": "drive-1", "name": "Documents"}]},
        )
        graph.get(f"{DRIVE}/root:/x.csv:/content", body=csv_bytes(n=[1]))

        result = make_pipeline(
            tmp_path,
            {"id": "x", "type": "read", "connection": "sp", "path": "x.csv"},
            site=site,
        ).run()

    assert result.artifact("x")["n"].tolist() == [1]


def test_site_must_be_an_address(tmp_path):
    with pytest.raises(ConfigError, match="should be the site's address"):
        make_pipeline(tmp_path, site="Finance")


def test_missing_extra_is_a_config_error(tmp_path, monkeypatch):
    monkeypatch.setattr(extras, "module_available", lambda _module: False)

    with pytest.raises(ConfigError, match=r"pip install 'dagcraft\[azure\]'"):
        make_pipeline(tmp_path)
