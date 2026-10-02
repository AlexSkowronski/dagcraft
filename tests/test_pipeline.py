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
        {"id": "people", "type": "read", "path": str(people_csv)},
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
            "path": str(output),
            "inputs": {"data": "names"},
        },
    )

    result = pipeline.run()

    assert result.success
    assert all(step.status == StepStatus.SUCCESS for step in result.steps.values())
    assert result.artifact("names")["name"].tolist() == ["Ada", "Grace"]

    # The index is not written by default, so only the selected column remains.
    written = pd.read_csv(output)
    assert written.columns.tolist() == ["name"]
    assert written["name"].tolist() == ["Ada", "Grace"]


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
        {"id": "people", "type": "read", "path": str(people_csv)},
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
        {"id": "people", "type": "read", "path": str(people_csv)},
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
            "path": str(tmp_path / "out.csv"),
            "inputs": {"data": "broken"},
        },
    )

    result = pipeline.run()

    assert not result.success
    assert result.steps["people"].status == StepStatus.SUCCESS
    assert result.steps["broken"].status == StepStatus.FAILED
    assert "no_such_column" in (result.steps["broken"].error or "")
    assert result.steps["save"].status == StepStatus.SKIPPED
    assert "save" not in result.artifacts
    assert not (tmp_path / "out.csv").exists()
