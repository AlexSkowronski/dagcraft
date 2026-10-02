import logging

import pandas as pd
import pytest

from dagcraft.cli import main


@pytest.fixture
def input_csv(tmp_path):
    path = tmp_path / "input.csv"
    pd.DataFrame({"value": [1, 2, 3]}).to_csv(path, index=False)
    return path


def write_pipeline(tmp_path, body):
    path = tmp_path / "pipeline.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_run_logs_every_step(tmp_path, input_csv, caplog):
    pipeline = write_pipeline(
        tmp_path,
        f"""
pipeline:
  name: demo
steps:
  - id: source
    type: read
    path: {input_csv.as_posix()}
  - id: sorted
    type: transform
    operation: sort
    inputs:
      data: source
    args:
      by: value
      ascending: false
""",
    )

    with caplog.at_level(logging.INFO):
        main(["run", str(pipeline)])

    summary = [
        record.getMessage()
        for record in caplog.records
        if record.name == "dagcraft.cli"
    ]
    assert any(line.startswith("SUCCESS    source") for line in summary)
    assert any(line.startswith("SUCCESS    sorted") for line in summary)
    assert summary[-1].startswith("SUCCESS in")


def test_run_failure_exits_nonzero(tmp_path, caplog):
    pipeline = write_pipeline(
        tmp_path,
        f"""
pipeline:
  name: demo
steps:
  - id: source
    type: read
    path: {(tmp_path / "missing.csv").as_posix()}
  - id: sorted
    type: transform
    operation: sort
    inputs:
      data: source
    args:
      by: value
""",
    )

    with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exc_info:
        main(["run", str(pipeline)])

    assert exc_info.value.code == 1

    summary = [record for record in caplog.records if record.name == "dagcraft.cli"]
    messages = [record.getMessage() for record in summary]
    assert any(line.startswith("FAILED     source") for line in messages)
    assert any(line.startswith("SKIPPED    sorted") for line in messages)
    assert messages[-1].startswith("FAILED in")
    assert summary[-1].levelno == logging.ERROR


def test_validate_valid_pipeline(tmp_path, input_csv, caplog):
    pipeline = write_pipeline(
        tmp_path,
        f"""
pipeline:
  name: demo
steps:
  - id: source
    type: read
    path: {input_csv.as_posix()}
""",
    )

    with caplog.at_level(logging.INFO):
        main(["validate", str(pipeline)])

    assert "Pipeline 'demo' is valid." in caplog.text


def test_invalid_config_exits_cleanly(tmp_path, caplog):
    pipeline = write_pipeline(
        tmp_path,
        """
pipeline:
  name: demo
steps:
  - id: source
    type: read
""",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["validate", str(pipeline)])

    assert exc_info.value.code == 1
    assert "Step 'source': path: Field required" in caplog.text
