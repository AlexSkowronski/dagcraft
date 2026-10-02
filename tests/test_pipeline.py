import sys
import types

import pandas as pd
import pytest

from dagcraft import Pipeline
from dagcraft.runtime import StepStatus


@pytest.fixture
def people_csv(tmp_path):
    path = tmp_path / "people.csv"
    pd.DataFrame(
        {
            "name": ["Ada", "Grace", "Linus", "Alan"],
            "salary": [120000, 115000, None, 98000],
        }
    ).to_csv(path, index=False)
    return path


def make_pipeline(*steps):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "steps": list(steps),
        }
    )


def test_read_transform_write(people_csv, tmp_path):
    output = tmp_path / "out.csv"

    pipeline = make_pipeline(
        {
            "id": "people",
            "type": "read",
            "connector": "csv",
            "args": {"filepath_or_buffer": str(people_csv)},
        },
        {
            "id": "clean",
            "type": "transform",
            "operation": "drop_nulls",
            "inputs": {"data": "people"},
        },
        {
            "id": "high_earners",
            "type": "transform",
            "operation": "filter",
            "inputs": {"data": "clean"},
            "args": {"expression": "salary > 100000"},
        },
        {
            "id": "names",
            "type": "transform",
            "operation": "select",
            "inputs": {"data": "high_earners"},
            "args": {"columns": ["name"]},
        },
        {
            "id": "save",
            "type": "write",
            "connector": "csv",
            "inputs": {"data": "names"},
            "args": {"path_or_buf": str(output), "index": False},
        },
    )

    result = pipeline.run()

    assert result.success
    assert all(step.status == StepStatus.SUCCESS for step in result.steps.values())
    assert result.artifact("names")["name"].tolist() == [
        "Ada",
        "Grace",
    ]
    assert pd.read_csv(output)["name"].tolist() == [
        "Ada",
        "Grace",
    ]


def test_python_step(people_csv, monkeypatch):
    module = types.ModuleType("dagcraft_test_helpers")
    monkeypatch.setattr(
        module,
        "count_rows",
        lambda data, offset=0: len(data) + offset,
        raising=False,
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)

    pipeline = make_pipeline(
        {
            "id": "people",
            "type": "read",
            "connector": "csv",
            "args": {"filepath_or_buffer": str(people_csv)},
        },
        {
            "id": "count",
            "type": "python",
            "callable": "dagcraft_test_helpers:count_rows",
            "inputs": {"data": "people"},
            "args": {"offset": 10},
        },
    )

    result = pipeline.run()

    assert result.success
    assert result.artifact("count") == 14


def test_failure_skips_remaining_steps(people_csv, tmp_path):
    pipeline = make_pipeline(
        {
            "id": "people",
            "type": "read",
            "connector": "csv",
            "args": {"filepath_or_buffer": str(people_csv)},
        },
        {
            "id": "broken",
            "type": "transform",
            "operation": "filter",
            "inputs": {"data": "people"},
            "args": {"expression": "no_such_column > 1"},
        },
        {
            "id": "save",
            "type": "write",
            "connector": "csv",
            "inputs": {"data": "broken"},
            "args": {"path_or_buf": str(tmp_path / "out.csv")},
        },
    )

    result = pipeline.run()

    assert not result.success
    assert result.steps["people"].status == StepStatus.SUCCESS
    assert result.steps["broken"].status == StepStatus.FAILED
    assert "no_such_column" in result.steps["broken"].error
    assert result.steps["save"].status == StepStatus.SKIPPED
    assert "save" not in result.artifacts


def test_unknown_step_type_fails_step_instead_of_raising():
    pipeline = make_pipeline(
        {"id": "mystery", "type": "does_not_exist"},
    )

    result = pipeline.run()

    assert not result.success
    assert result.steps["mystery"].status == StepStatus.FAILED
    assert "Unknown step type" in result.steps["mystery"].error


def test_unknown_operation_fails_step():
    pipeline = make_pipeline(
        {
            "id": "t",
            "type": "transform",
            "operation": "does_not_exist",
        },
    )

    result = pipeline.run()

    assert not result.success
    assert "Unknown operation" in result.steps["t"].error
