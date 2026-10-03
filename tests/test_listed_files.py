import json
import sys
import threading
import time
import types
from pathlib import Path

import fsspec
import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline, RunError
from dagcraft.config.connections import AzureBlobConfig
from dagcraft.connections import AzureBlobConnection, LocalConnection
from dagcraft.exceptions import ExecutionError


@pytest.fixture(autouse=True)
def files(tmp_path):
    """
    Three day files, and a table listing two of them.
    """
    (tmp_path / "events").mkdir()
    for day in (1, 2, 3):
        (tmp_path / "events" / f"{day}.json").write_text(
            json.dumps({"day": day, "events": [{"id": day * 10}]})
        )
    pd.DataFrame({"blob_path": ["events/1.json", "events/3.json"], "n": [1, 2]}).to_csv(
        tmp_path / "pending.csv", index=False
    )


def pipeline(tmp_path, *steps):
    return Pipeline.from_dict(
        {"pipeline": {"name": "listed"}, "steps": list(steps)}, base_dir=tmp_path
    )


PENDING = {"id": "pending", "type": "read", "path": "pending.csv"}


def listed(**fields):
    return {
        "id": "batches",
        "type": "read",
        "inputs": {"paths": "pending"},
        "path_column": "blob_path",
        **fields,
    }


def test_reads_the_files_a_table_lists(tmp_path):
    result = pipeline(tmp_path, PENDING, listed(source_column="file")).run()

    assert result.output("batches") == [
        {"day": 1, "events": [{"id": 10}], "file": "events/1.json"},
        {"day": 3, "events": [{"id": 30}], "file": "events/3.json"},
    ]


def test_reads_the_files_a_list_names(tmp_path, monkeypatch):
    module = types.ModuleType("dagcraft_listed_helpers")
    module.recent = lambda _data: ["events/2.json"]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)

    result = pipeline(
        tmp_path,
        PENDING,
        {
            "id": "paths",
            "type": "transform",
            "inputs": {"data": "pending"},
            "operations": [{"python": "dagcraft_listed_helpers:recent"}],
        },
        {"id": "batches", "type": "read", "inputs": {"paths": "paths"}},
    ).run()

    assert result.output("batches") == [{"day": 2, "events": [{"id": 20}]}]


def test_a_one_column_table_needs_no_path_column(tmp_path):
    pd.DataFrame({"path": ["events/2.json"]}).to_csv(tmp_path / "one.csv", index=False)
    result = pipeline(
        tmp_path,
        {"id": "pending", "type": "read", "path": "one.csv"},
        {"id": "batches", "type": "read", "inputs": {"paths": "pending"}},
    ).run()

    assert result.output("batches")[0]["day"] == 2


def test_the_plan_names_the_listing_step(tmp_path):
    plan = pipeline(tmp_path, PENDING, listed()).plan()

    assert plan[1].description == "read the files 'pending' lists from 'local'"


def test_files_are_read_in_parallel_in_order(tmp_path, monkeypatch):
    threads = set()
    original = LocalConnection.open_file

    def slow_open(self, path, mode):
        threads.add(threading.current_thread().name)
        time.sleep(0.05)
        return original(self, path, mode)

    monkeypatch.setattr(LocalConnection, "open_file", slow_open)
    days = pd.DataFrame({"path": [f"events/{d}.json" for d in (3, 1, 2)]})
    days.to_csv(tmp_path / "days.csv", index=False)

    result = pipeline(
        tmp_path,
        {"id": "days", "type": "read", "path": "days.csv"},
        {"id": "batches", "type": "read", "inputs": {"paths": "days"}, "parallel": 3},
    ).run()

    assert [document["day"] for document in result.output("batches")] == [3, 1, 2]
    assert len({name for name in threads if name.startswith("dagcraft-files")}) > 1


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            {"blob_path": ["events/1.json", None]},
            "1 path in the 'paths' input is missing",
        ),
        ({"blob_path": ["events/1.json", "events/9.json"]}, "9.json"),
        ({"blob_path": ["events/1.json", "pending.csv"]}, "different formats"),
        ({"other": ["events/1.json"]}, "path_column 'blob_path' isn't in the 'paths'"),
    ],
)
def test_problems_with_the_list_fail_the_step(tmp_path, rows, message):
    pd.DataFrame(rows).to_csv(tmp_path / "pending.csv", index=False)

    with pytest.raises(RunError) as exc_info:
        pipeline(tmp_path, PENDING, listed()).run()

    assert message in str(exc_info.value)


def test_format_reads_mixed_names_one_way(tmp_path):
    (tmp_path / "events" / "4.txt").write_text(json.dumps({"day": 4}))
    pd.DataFrame({"blob_path": ["events/1.json", "events/4.txt"]}).to_csv(
        tmp_path / "pending.csv", index=False
    )

    result = pipeline(tmp_path, PENDING, listed(format="json")).run()

    assert [document["day"] for document in result.output("batches")] == [1, 4]


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (listed(path="events/*.json"), "Set 'path' or give a 'paths' input, not both."),
        (
            {"id": "batches", "type": "read", "path": "x.json", "path_column": "p"},
            "'path_column' only applies with a 'paths' input.",
        ),
        (
            {"id": "batches", "type": "read", "inputs": {"data": "pending"}},
            "A read step's only input is 'paths'",
        ),
    ],
)
def test_listed_reads_are_checked_when_the_pipeline_loads(tmp_path, step, message):
    with pytest.raises(ConfigError) as exc_info:
        pipeline(tmp_path, PENDING, step)

    assert message in str(exc_info.value)


def test_sql_connections_cant_take_paths(tmp_path):
    with pytest.raises(ConfigError, match="doesn't read files"):
        Pipeline.from_dict(
            {
                "pipeline": {"name": "listed"},
                "connections": {"db": {"type": "sql", "url": "sqlite:///x.db"}},
                "steps": [
                    PENDING,
                    {
                        "id": "rows",
                        "type": "read",
                        "connection": "db",
                        "table": "t",
                        "inputs": {"paths": "pending"},
                    },
                ],
            },
            base_dir=tmp_path,
        )


def blob(**config):
    return AzureBlobConnection(
        "lake", AzureBlobConfig(container="raw", **config), Path()
    )


@pytest.mark.parametrize(
    ("config", "path", "expected"),
    [
        ({"account": "acct"}, "events/a.json", "events/a.json"),
        (
            {"account": "acct"},
            "https://acct.blob.core.windows.net/raw/events/2026%2010/a.json",
            "events/2026 10/a.json",
        ),
        (
            {"account": "acct", "prefix": "landing"},
            "https://acct.dfs.core.windows.net/raw/landing/events/a.json",
            "events/a.json",
        ),
        (
            {"connection_string": "AccountName=acct;AccountKey=a2V5"},
            "https://acct.blob.core.windows.net/raw/a.json",
            "a.json",
        ),
    ],
)
def test_blob_urls_become_paths_in_the_container(config, path, expected):
    assert blob(**config).relative_path(path) == expected


@pytest.mark.parametrize(
    ("config", "url", "message"),
    [
        (
            {"account": "acct"},
            "https://other.blob.core.windows.net/raw/a.json",
            "reads container 'raw' of account 'acct'",
        ),
        (
            {"account": "acct"},
            "https://acct.blob.core.windows.net/archive/a.json",
            "reads container 'raw'",
        ),
        (
            {"account": "acct", "prefix": "landing"},
            "https://acct.blob.core.windows.net/raw/elsewhere/a.json",
            "reads under 'landing/'",
        ),
    ],
)
def test_blob_urls_elsewhere_are_refused(config, url, message):
    with pytest.raises(ExecutionError, match=message):
        blob(**config).relative_path(url)


def test_reads_blobs_listed_as_urls(tmp_path, monkeypatch):
    filesystem = fsspec.filesystem("memory", skip_instance_cache=True)
    filesystem.store.clear()
    filesystem.pipe("raw/events/a.json", b'{"id": 1}')
    monkeypatch.setattr(AzureBlobConnection, "create_filesystem", lambda _: filesystem)
    pd.DataFrame(
        {"url": ["https://acct.blob.core.windows.net/raw/events/a.json"]}
    ).to_csv(tmp_path / "urls.csv", index=False)

    result = Pipeline.from_dict(
        {
            "pipeline": {"name": "urls"},
            "connections": {
                "lake": {"type": "azure_blob", "account": "acct", "container": "raw"}
            },
            "steps": [
                {"id": "urls", "type": "read", "path": "urls.csv"},
                {
                    "id": "docs",
                    "type": "read",
                    "connection": "lake",
                    "inputs": {"paths": "urls"},
                },
            ],
        },
        base_dir=tmp_path,
    ).run()

    assert result.output("docs") == [{"id": 1}]
    filesystem.store.clear()
