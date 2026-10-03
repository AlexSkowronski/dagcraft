import json

import fsspec
import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline, RunError
from dagcraft.connections import AzureBlobConnection


def make_pipeline(base_dir, *steps, connections=None):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "connections": connections or {},
            "steps": list(steps),
        },
        base_dir=base_dir,
    )


def write_events(folder, name, *ids):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps([{"id": i} for i in ids]))


@pytest.fixture
def events(tmp_path):
    write_events(tmp_path / "events", "2026-10-02.json", 3)
    write_events(tmp_path / "events", "2026-10-01.json", 1, 2)
    write_events(tmp_path / "events" / "late", "2026-10-03.json", 4)
    (tmp_path / "events" / "notes.txt").write_text("not json")
    # A folder whose name matches the pattern is not read as a file.
    (tmp_path / "events" / "folder.json").mkdir()


@pytest.mark.usefixtures("events")
def test_wildcard_json_gives_a_list_of_documents_in_order(tmp_path):
    documents = (
        make_pipeline(
            tmp_path,
            {
                "id": "events",
                "type": "read",
                "path": "events/*.json",
                "source_column": "file",
            },
        )
        .run()
        .output("events")
    )

    # Each file holds a list of objects, and each object names its file.
    assert documents == [
        [
            {"id": 1, "file": "events/2026-10-01.json"},
            {"id": 2, "file": "events/2026-10-01.json"},
        ],
        [{"id": 3, "file": "events/2026-10-02.json"}],
    ]


def test_wildcard_tables_are_stacked_into_one(tmp_path):
    (tmp_path / "daily").mkdir()
    for day, ids in {"02": [3], "01": [1, 2]}.items():
        pd.DataFrame({"id": ids}).to_csv(tmp_path / "daily" / f"{day}.csv", index=False)

    frame = (
        make_pipeline(
            tmp_path,
            {
                "id": "days",
                "type": "read",
                "path": "daily/*.csv",
                "source_column": "file",
            },
        )
        .run()
        .output("days")
    )

    assert frame.to_dict("list") == {
        "id": [1, 2, 3],
        "file": ["daily/01.csv", "daily/01.csv", "daily/02.csv"],
    }


def test_wildcard_json_lines_give_one_list_of_records(tmp_path):
    for day, ids in {"02": [3], "01": [1, 2]}.items():
        lines = "".join(json.dumps({"id": i}) + "\n" for i in ids)
        (tmp_path / f"{day}.jsonl").write_text(lines)

    records = (
        make_pipeline(tmp_path, {"id": "lines", "type": "read", "path": "*.jsonl"})
        .run()
        .output("lines")
    )

    assert records == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_source_column_needs_objects(tmp_path):
    (tmp_path / "a.json").write_text('"just text"')

    pipeline = make_pipeline(
        tmp_path,
        {"id": "docs", "type": "read", "path": "*.json", "source_column": "file"},
    )

    with pytest.raises(RunError, match=r"source_column needs a\.json to hold objects"):
        pipeline.run()


@pytest.mark.usefixtures("events")
def test_double_star_matches_any_depth(tmp_path):
    documents = (
        make_pipeline(
            tmp_path,
            {"id": "events", "type": "read", "path": "events/**/*.json"},
        )
        .run()
        .output("events")
    )

    assert sorted(record["id"] for document in documents for record in document) == [
        1,
        2,
        3,
        4,
    ]


@pytest.mark.usefixtures("events")
def test_no_matches_is_an_error(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        {"id": "events", "type": "read", "path": "events/2025-*.json"},
    )

    with pytest.raises(RunError, match="No files in connection 'local' match"):
        pipeline.run()


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (
            {"type": "read", "path": "events.json", "source_column": "file"},
            "'source_column' only applies when 'path' has wildcards.",
        ),
        (
            {"type": "write", "path": "out/*.json", "inputs": {"data": "source"}},
            "A path to write can't contain wildcards",
        ),
    ],
)
def test_wildcard_validation(tmp_path, step, message):
    with pytest.raises(ConfigError) as exc_info:
        make_pipeline(
            tmp_path,
            {"id": "source", "type": "read", "path": "in.json"},
            {"id": "step", **step},
        )

    assert message in str(exc_info.value)


@pytest.fixture
def memory_container(monkeypatch):
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


def test_wildcards_in_blob_storage(tmp_path, memory_container):
    for day, ids in {"01": [1], "02": [2, 3]}.items():
        with memory_container.open(f"raw/landing/events/2026-10-{day}.json", "wb") as f:
            f.write(json.dumps([{"id": i} for i in ids]).encode())

    documents = (
        make_pipeline(
            tmp_path,
            {
                "id": "events",
                "type": "read",
                "connection": "lake",
                "path": "events/*.json",
                "source_column": "blob",
            },
            connections={
                "lake": {
                    "type": "azure_blob",
                    "account": "acct",
                    "container": "raw",
                    "prefix": "landing",
                }
            },
        )
        .run()
        .output("events")
    )

    records = [record for document in documents for record in document]
    assert [record["id"] for record in records] == [1, 2, 3]
    assert [record["blob"] for record in records] == [
        "events/2026-10-01.json",
        "events/2026-10-02.json",
        "events/2026-10-02.json",
    ]
