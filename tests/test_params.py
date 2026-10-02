import datetime
import logging

import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline
from dagcraft.cli import main, parse_param


@pytest.fixture
def numbers_csv(tmp_path):
    pd.DataFrame({"n": [3, 1, 2], "label": ["c", "a", "b"]}).to_csv(
        tmp_path / "numbers.csv", index=False
    )


def make_pipeline(tmp_path, *steps, params=None, overrides=None, connections=None):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "params": params or {},
            "connections": connections or {},
            "steps": list(steps),
        },
        base_dir=tmp_path,
        params=overrides,
    )


@pytest.mark.usefixtures("numbers_csv")
def test_references_inside_text_and_as_whole_values(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        {"id": "source", "type": "read", "path": "${params.name}.csv"},
        {
            "id": "picked",
            "type": "transform",
            "operation": "select",
            "inputs": {"data": "source"},
            "args": {"columns": "${params.columns}"},
        },
        {
            "id": "big",
            "type": "transform",
            "operation": "filter",
            "inputs": {"data": "picked"},
            "args": {"expression": "n >= ${params.minimum}"},
        },
        params={"name": "numbers", "columns": ["n"], "minimum": 2},
    )

    result = pipeline.run()

    # A whole-value reference keeps its type: the list stays a list.
    assert result.artifact("big").to_dict("list") == {"n": [3, 2]}


@pytest.mark.usefixtures("numbers_csv")
def test_overrides_replace_the_files_params(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        {
            "id": "sorted",
            "type": "transform",
            "operation": "sort",
            "inputs": {"data": "source"},
            "args": {"by": "n", "ascending": "${params.ascending}"},
        },
        {"id": "source", "type": "read", "path": "numbers.csv"},
        params={"ascending": True},
        overrides={"ascending": False},
    )

    assert pipeline.params == {"ascending": False}
    assert pipeline.run().artifact("sorted")["n"].tolist() == [3, 2, 1]


def test_unknown_override_is_rejected(tmp_path):
    with pytest.raises(
        ConfigError, match=r"Unknown parameter: run_dat\. Defined: run_date"
    ):
        make_pipeline(
            tmp_path,
            params={"run_date": "2026-10-02"},
            overrides={"run_dat": "2026-10-03"},
        )


@pytest.mark.usefixtures("numbers_csv")
def test_environment_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_NAME", "numbers")
    monkeypatch.delenv("DAGCRAFT_UNSET", raising=False)

    pipeline = make_pipeline(
        tmp_path,
        {"id": "source", "type": "read", "path": "${env:DATA_NAME}.csv"},
        params={"region": "${env:DAGCRAFT_UNSET:-north}"},
    )

    assert pipeline.params == {"region": "north"}
    assert len(pipeline.run().artifact("source")) == 3


def test_escaped_reference_is_kept_literally(tmp_path):
    (tmp_path / "${literal}.csv").write_text("n\n1\n", encoding="utf-8")

    pipeline = make_pipeline(
        tmp_path,
        {"id": "source", "type": "read", "path": "$${literal}.csv"},
    )

    assert pipeline.run().artifact("source")["n"].tolist() == [1]


@pytest.mark.usefixtures("numbers_csv")
def test_connections_can_use_params(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "numbers.csv").rename(tmp_path / "data" / "numbers.csv")

    pipeline = make_pipeline(
        tmp_path,
        {"id": "source", "type": "read", "connection": "files", "path": "numbers.csv"},
        params={"folder": "data"},
        connections={"files": {"type": "local", "root": "${params.folder}"}},
    )

    assert len(pipeline.run().artifact("source")) == 3


@pytest.mark.parametrize(
    ("step", "params", "message"),
    [
        (
            {"id": "a", "type": "read", "path": "${params.run_dat}.csv"},
            {"run_date": "x"},
            "Step 'a': in path: unknown parameter 'run_dat'. Defined: run_date.",
        ),
        (
            {"id": "a", "type": "read", "path": "${env:DAGCRAFT_UNSET}.csv"},
            {},
            "Step 'a': in path: environment variable 'DAGCRAFT_UNSET' is not set.",
        ),
        (
            {"id": "a", "type": "read", "path": "${run_date}.csv"},
            {},
            "isn't a reference dagcraft understands",
        ),
        (
            {"id": "a", "type": "read", "path": "x_${params.cols}.csv"},
            {"cols": ["a", "b"]},
            "is a list and can only be used as a whole value",
        ),
    ],
)
def test_reference_errors(tmp_path, monkeypatch, step, params, message):
    monkeypatch.delenv("DAGCRAFT_UNSET", raising=False)

    with pytest.raises(ConfigError) as exc_info:
        make_pipeline(tmp_path, step, params=params)

    assert message in str(exc_info.value)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"a": "1", "b": "${params.a}"}, "Parameter 'b': params can't reference"),
        ({"run-date": "x"}, "Parameter name 'run-date' should be letters"),
    ],
)
def test_param_errors(tmp_path, params, message):
    with pytest.raises(ConfigError, match=message):
        make_pipeline(tmp_path, params=params)


@pytest.mark.usefixtures("numbers_csv")
def test_cli_param_overrides(tmp_path, caplog):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        """
pipeline:
  name: cli
params:
  minimum: 0
  day: 2026-01-01
steps:
  - id: source
    type: read
    path: numbers.csv
  - id: big
    type: transform
    operation: filter
    inputs: {data: source}
    args: {expression: "n >= ${params.minimum}"}
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        main(["validate", str(path), "--param", "minimum=3"])

    assert "Pipeline 'cli' is valid." in caplog.text

    # Values are read as YAML, like the file.
    pipeline = Pipeline.from_yaml(path, params={"minimum": 3})
    assert pipeline.params == {"minimum": 3, "day": datetime.date(2026, 1, 1)}


def test_cli_rejects_malformed_param(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path / "pipeline.yaml"), "--param", "minimum"])

    assert exc_info.value.code == 2
    assert "expected NAME=VALUE" in capsys.readouterr().err


def test_cli_param_values_are_parsed_as_yaml():
    assert parse_param("limit=10") == ("limit", 10)
    assert parse_param("columns=[a, b]") == ("columns", ["a", "b"])
    assert parse_param("day=2026-10-02") == ("day", datetime.date(2026, 10, 2))
    assert parse_param("flag=on") == ("flag", "on")
    assert parse_param("empty=") == ("empty", "")
