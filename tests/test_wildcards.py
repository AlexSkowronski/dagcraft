import json

import fsspec
import pytest

from dagcraft import ConfigError, Pipeline, PipelineError
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
def test_wildcard_reads_every_matching_file_in_order(tmp_path):
    frame = (
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
        .artifact("events")
    )

    assert frame.to_dict("list") == {
        "id": [1, 2, 3],
        "file": [
            "events/2026-10-01.json",
            "events/2026-10-01.json",
            "events/2026-10-02.json",
        ],
    }


@pytest.mark.usefixtures("events")
def test_double_star_matches_any_depth(tmp_path):
    frame = (
        make_pipeline(
            tmp_path,
            {"id": "events", "type": "read", "path": "events/**/*.json"},
        )
        .run()
        .artifact("events")
    )

    assert sorted(frame["id"]) == [1, 2, 3, 4]


@pytest.mark.usefixtures("events")
def test_no_matches_is_an_error(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        {"id": "events", "type": "read", "path": "events/2025-*.json"},
    )

    with pytest.raises(PipelineError, match="No files in connection 'local' match"):
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

    frame = (
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
        .artifact("events")
    )

    assert frame["id"].tolist() == [1, 2, 3]
    assert frame["blob"].tolist() == [
        "events/2026-10-01.json",
        "events/2026-10-02.json",
        "events/2026-10-02.json",
    ]
