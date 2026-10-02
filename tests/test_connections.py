from typing import ClassVar

import pandas as pd
import pytest
from pydantic import BaseModel, ConfigDict

from dagcraft import Connection, Pipeline, PipelineError, register_connection
from dagcraft.exceptions import ConfigError


class RecordingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


@register_connection("recording")
class RecordingConnection(Connection):
    """Read-only test connection that records its lifecycle."""

    config_model = RecordingConfig
    read_options = RecordingOptions

    events: ClassVar[list[str]] = []

    def open(self) -> None:
        self.events.append(f"open {self.name}")

    def close(self) -> None:
        self.events.append(f"close {self.name}")

    def read(self, options: RecordingOptions) -> int:
        self.events.append(f"read {self.name}")
        return options.value


@pytest.fixture(autouse=True)
def clear_events():
    RecordingConnection.events.clear()


def make_pipeline(*steps, connections=None, base_dir=None):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "connections": connections or {},
            "steps": list(steps),
        },
        base_dir=base_dir,
    )


def write_csv(path, **columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns).to_csv(path, index=False)


def test_paths_are_relative_to_the_pipeline_file(tmp_path, monkeypatch):
    project = tmp_path / "project"
    write_csv(project / "data" / "in.csv", value=[3, 1, 2])
    (project / "pipeline.yaml").write_text(
        """
pipeline:
  name: relative
steps:
  - id: source
    type: read
    path: data/in.csv
  - id: save
    type: write
    path: out/nested/result.parquet
    inputs:
      data: source
""",
        encoding="utf-8",
    )

    # Run from somewhere else to prove paths don't depend on the cwd.
    monkeypatch.chdir(tmp_path)
    result = Pipeline.from_yaml("project/pipeline.yaml").run()

    assert result.success
    written = pd.read_parquet(project / "out" / "nested" / "result.parquet")
    assert written["value"].tolist() == [3, 1, 2]


def test_named_local_connection_uses_its_root(tmp_path):
    write_csv(tmp_path / "raw" / "in.csv", value=[1, 2])

    pipeline = make_pipeline(
        {"id": "source", "type": "read", "connection": "raw", "path": "in.csv"},
        connections={"raw": {"type": "local", "root": "raw"}},
        base_dir=tmp_path,
    )

    result = pipeline.run()

    assert result.success
    assert result.artifact("source")["value"].tolist() == [1, 2]


def test_format_can_be_set_explicitly(tmp_path):
    write_csv(tmp_path / "in.csv", value=[1, 2])

    pipeline = make_pipeline(
        {"id": "source", "type": "read", "path": "in.csv"},
        {
            "id": "save",
            "type": "write",
            "path": "export.dat",
            "format": "csv",
            "inputs": {"data": "source"},
        },
        base_dir=tmp_path,
    )

    assert pipeline.run().success
    assert pd.read_csv(tmp_path / "export.dat")["value"].tolist() == [1, 2]


def test_format_args_are_passed_through(tmp_path):
    (tmp_path / "in.csv").write_text("a;b\n1;2\n", encoding="utf-8")

    pipeline = make_pipeline(
        {
            "id": "source",
            "type": "read",
            "path": "in.csv",
            "args": {"sep": ";"},
        },
        base_dir=tmp_path,
    )

    result = pipeline.run()

    assert result.success
    assert result.artifact("source").columns.tolist() == ["a", "b"]


def test_connection_opened_once_and_closed_after_run():
    pipeline = make_pipeline(
        {"id": "a", "type": "read", "connection": "rec", "value": 1},
        {"id": "b", "type": "read", "connection": "rec", "value": 2},
        connections={
            "rec": {"type": "recording"},
            "unused": {"type": "recording"},
        },
    )

    result = pipeline.run()

    assert result.success
    assert result.artifact("b") == 2
    # "unused" is never opened because no step uses it.
    assert RecordingConnection.events == [
        "open rec",
        "read rec",
        "read rec",
        "close rec",
    ]


def test_connections_reopen_for_each_run():
    pipeline = make_pipeline(
        {"id": "a", "type": "read", "connection": "rec", "value": 1},
        connections={"rec": {"type": "recording"}},
    )

    pipeline.run()
    pipeline.run()

    assert (
        RecordingConnection.events
        == [
            "open rec",
            "read rec",
            "close rec",
        ]
        * 2
    )


def test_connection_closed_when_a_step_fails():
    pipeline = make_pipeline(
        {"id": "a", "type": "read", "connection": "rec", "value": 1},
        {
            "id": "boom",
            "type": "transform",
            "operation": "filter",
            "inputs": {"data": "a"},
            "args": {"expression": "x > 1"},
        },
        connections={"rec": {"type": "recording"}},
    )

    with pytest.raises(PipelineError):
        pipeline.run()

    assert RecordingConnection.events[-1] == "close rec"


def test_connection_options_are_validated_at_compile_time():
    with pytest.raises(ConfigError, match="value: Field required"):
        make_pipeline(
            {"id": "a", "type": "read", "connection": "rec"},
            connections={"rec": {"type": "recording"}},
        )


def test_write_to_read_only_connection_rejected():
    with pytest.raises(ConfigError, match="does not support writing"):
        make_pipeline(
            {"id": "a", "type": "read", "connection": "rec", "value": 1},
            {
                "id": "b",
                "type": "write",
                "connection": "rec",
                "inputs": {"data": "a"},
            },
            connections={"rec": {"type": "recording"}},
        )


def test_failed_local_write_leaves_the_old_file(tmp_path):
    (tmp_path / "out.csv").write_text("old contents\n", encoding="utf-8")
    write_csv(tmp_path / "in.csv", value=[1, 2])

    pipeline = make_pipeline(
        {"id": "source", "type": "read", "path": "in.csv"},
        {
            "id": "save",
            "type": "write",
            "path": "out.csv",
            "inputs": {"data": "source"},
            # An argument to_csv doesn't accept makes the write fail part-way.
            "args": {"no_such_argument": True},
        },
        base_dir=tmp_path,
    )

    with pytest.raises(PipelineError):
        pipeline.run()

    assert (tmp_path / "out.csv").read_text(encoding="utf-8") == "old contents\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["in.csv", "out.csv"]


def test_local_write_replaces_the_file(tmp_path):
    (tmp_path / "out.csv").write_text("old contents\n", encoding="utf-8")
    write_csv(tmp_path / "in.csv", value=[1, 2])

    make_pipeline(
        {"id": "source", "type": "read", "path": "in.csv"},
        {
            "id": "save",
            "type": "write",
            "path": "out.csv",
            "inputs": {"data": "source"},
        },
        base_dir=tmp_path,
    ).run()

    assert pd.read_csv(tmp_path / "out.csv")["value"].tolist() == [1, 2]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["in.csv", "out.csv"]
