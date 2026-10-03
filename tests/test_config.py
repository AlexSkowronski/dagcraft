import io

import pandas as pd
import pytest

from dagcraft import Pipeline
from dagcraft.exceptions import ConfigError
from dagcraft.yaml_loader import load_yaml


def make_config(*steps, connections=None):
    config = {
        "pipeline": {"name": "test"},
        "steps": list(steps),
    }
    if connections is not None:
        config["connections"] = connections
    return config


def test_valid_config_compiles():
    pipeline = Pipeline.from_dict(
        make_config(
            {"id": "src", "type": "read", "path": "data.csv"},
        )
    )

    assert pipeline.config.pipeline.name == "test"
    assert list(pipeline.compiled.steps) == ["src"]
    assert "local" in pipeline.compiled.connections


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (
            {"id": "a"},
            "Step 'a' needs a 'type'.",
        ),
        (
            {"type": "read", "path": "x.csv"},
            "Step #1: id: Field required",
        ),
        (
            {"id": "a", "type": "nope"},
            "Step 'a': Unknown step type: 'nope'",
        ),
        (
            {"id": "a", "type": "read"},
            "Step 'a': Set 'path', or give a 'paths' input listing the files",
        ),
        (
            {"id": "a", "type": "read", "path": "x.csv", "pth": "y.csv"},
            "pth: Extra inputs are not permitted",
        ),
        (
            {"id": "a", "type": "read", "path": "x.csv", "inputs": {"data": "b"}},
            "A read step's only input is 'paths'",
        ),
        (
            {"id": "a", "type": "read", "path": "notes.txt"},
            "Cannot infer a format from 'notes.txt'",
        ),
        (
            {"id": "a", "type": "read", "path": "x.csv", "format": "xml"},
            "Unknown format: 'xml'",
        ),
        (
            {"id": "a", "type": "read", "path": "x.csv", "connection": "nope"},
            "Unknown connection 'nope'",
        ),
        (
            {"id": "a", "type": "write", "path": "x.csv"},
            "A write step needs at least one input.",
        ),
        (
            {
                "id": "a",
                "type": "write",
                "path": "x.csv",
                "inputs": {"first": "b", "second": "c"},
            },
            "Only formats that hold several tables, such as excel",
        ),
        (
            {"id": "a", "type": "transform", "inputs": {"data": "b"}},
            "operations: Field required",
        ),
        (
            {
                "id": "a",
                "type": "python",
                "callable": "dagcraft:Pipeline",
                "inputs": {"data": "b"},
                "args": {"data": 1},
            },
            "Names used in both inputs and args: data",
        ),
        (
            {"id": "a", "type": "python"},
            "callable: Field required",
        ),
        (
            {"id": "a", "type": "python", "callable": "no_colon"},
            "must use the format 'module.path:function_name'",
        ),
        (
            {"id": "a", "type": "python", "callable": "dagcraft_no_such_module:f"},
            "Could not import module 'dagcraft_no_such_module'",
        ),
        (
            {"id": "a", "type": "python", "callable": "dagcraft:no_such_function"},
            "has no callable named 'no_such_function'",
        ),
    ],
)
def test_step_validation_messages(step, message):
    with pytest.raises(ConfigError) as exc_info:
        Pipeline.from_dict(make_config(step))

    assert message in str(exc_info.value)


@pytest.mark.parametrize(
    ("connections", "message"),
    [
        (
            {"data": {"root": "x"}},
            "Connection 'data' needs a 'type'.",
        ),
        (
            {"data": {"type": "nope"}},
            "Connection 'data': Unknown connection type: 'nope'",
        ),
        (
            {"data": {"type": "local", "rooot": "x"}},
            "Connection 'data': rooot: Extra inputs are not permitted",
        ),
    ],
)
def test_connection_validation_messages(connections, message):
    step = {"id": "a", "type": "read", "path": "x.csv"}

    with pytest.raises(ConfigError) as exc_info:
        Pipeline.from_dict(make_config(step, connections=connections))

    assert message in str(exc_info.value)


def test_duplicate_step_ids_rejected():
    step = {"id": "a", "type": "read", "path": "x.csv"}

    with pytest.raises(ConfigError, match="Duplicate step id: 'a'"):
        Pipeline.from_dict(make_config(step, step))


def test_unknown_top_level_fields_rejected():
    config = make_config()
    config["schedule"] = "daily"

    with pytest.raises(
        ConfigError,
        match="schedule: Extra inputs are not permitted",
    ):
        Pipeline.from_dict(config)


def test_from_yaml_missing_file(tmp_path):
    with pytest.raises(
        ConfigError,
        match="Could not read pipeline file",
    ):
        Pipeline.from_yaml(tmp_path / "missing.yaml")


def test_from_yaml_invalid_yaml(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("steps: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid YAML"):
        Pipeline.from_yaml(path)


def test_from_yaml_empty_file(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid pipeline"):
        Pipeline.from_yaml(path)


def test_only_true_and_false_are_booleans_in_yaml():
    loaded = load_yaml(
        io.StringIO(
            "on: id\n"
            "values: [yes, no, on, off, NO, true, false, True]\n"
            "ascending: false\n"
        )
    )

    assert loaded == {
        "on": "id",
        "values": ["yes", "no", "on", "off", "NO", True, False, True],
        "ascending": False,
    }


def test_join_on_works_from_yaml(tmp_path):
    pd.DataFrame({"id": [1, 2], "a": ["x", "y"]}).to_csv(
        tmp_path / "left.csv", index=False
    )
    pd.DataFrame({"id": [2, 1], "b": ["q", "p"]}).to_csv(
        tmp_path / "right.csv", index=False
    )
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        """
pipeline:
  name: join
steps:
  - id: left
    type: read
    path: left.csv
  - id: right
    type: read
    path: right.csv
  - id: joined
    type: transform
    inputs: {data: left, right: right}
    operations:
      - join: {right: right, on: id, how: left}
""",
        encoding="utf-8",
    )

    joined = Pipeline.from_yaml(path).run().output("joined")

    assert joined.to_dict("list") == {"id": [1, 2], "a": ["x", "y"], "b": ["p", "q"]}
