import logging
import re
import subprocess
import sys

import pandas as pd
import pytest

from dagcraft import __version__
from dagcraft.cli import ExitCode, main


@pytest.fixture
def input_csv(tmp_path):
    path = tmp_path / "input.csv"
    pd.DataFrame({"value": [1, 2, 3]}).to_csv(path, index=False)
    return path


def write_pipeline(tmp_path, body):
    path = tmp_path / "pipeline.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def report_lines(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "dagcraft.cli.report"
    ]


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
        assert main([str(pipeline)]) == ExitCode.SUCCESS

    summary = report_lines(caplog)
    assert summary[0] == "Pipeline 'demo' is valid."
    assert any(line.startswith("SUCCESS    source") for line in summary)
    assert any(line.startswith("SUCCESS    sorted") for line in summary)
    assert summary[-1].startswith("SUCCESS in")


def test_run_failure_exits_1(tmp_path, caplog):
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

    with caplog.at_level(logging.INFO):
        assert main([str(pipeline)]) == ExitCode.FAILED

    summary = [r for r in caplog.records if r.name == "dagcraft.cli.report"]
    messages = [record.getMessage() for record in summary]
    assert any(line.startswith("FAILED     source") for line in messages)
    assert any(line.startswith("SKIPPED    sorted") for line in messages)
    assert messages[-1].startswith("FAILED in")
    assert summary[-1].levelno == logging.ERROR


def test_dry_run_shows_the_plan_without_running(tmp_path, input_csv, caplog):
    pipeline = write_pipeline(
        tmp_path,
        f"""
pipeline:
  name: demo
params:
  limit: 2
steps:
  - id: save
    type: write
    path: out/sorted.csv
    inputs: {{data: sorted}}
  - id: source
    type: read
    path: {input_csv.as_posix()}
  - id: sorted
    type: transform
    operation: sort
    inputs: {{data: source}}
    args: {{by: value}}
""",
    )

    with caplog.at_level(logging.INFO):
        assert main([str(pipeline), "--dry-run"]) == ExitCode.SUCCESS

    assert report_lines(caplog) == [
        "Pipeline 'demo' is valid.",
        "Params: limit=2",
        "Steps, in run order:",
        f"  1. source  read {input_csv.as_posix()} from 'local'",
        "  2. sorted  transform with 'sort'  <- data: source",
        "  3. save    write out/sorted.csv to 'local'  <- data: sorted",
        "Dry run: nothing was run.",
    ]
    assert not (tmp_path / "out").exists()


def test_invalid_config_exits_2(tmp_path, caplog):
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

    assert main([str(pipeline), "--dry-run"]) == ExitCode.INVALID
    assert "Step 'source': path: Field required" in caplog.text


def test_missing_file_exits_2(tmp_path, caplog):
    assert main([str(tmp_path / "nowhere.yaml")]) == ExitCode.INVALID
    assert "Could not read pipeline file" in caplog.text


def test_verbose_logs_detail(tmp_path, caplog):
    for day in (1, 2):
        pd.DataFrame({"n": [day]}).to_csv(tmp_path / f"day{day}.csv", index=False)
    pipeline = write_pipeline(
        tmp_path,
        "pipeline: {name: demo}\n"
        "steps:\n"
        "  - {id: days, type: read, path: 'day*.csv'}\n",
    )

    with caplog.at_level(logging.DEBUG):
        assert main([str(pipeline), "-v"]) == ExitCode.SUCCESS

    messages = [record.getMessage() for record in caplog.records]
    run_prefix = r"\[demo [0-9a-f]{8}\] days: "
    assert any(re.match(f"{run_prefix}found 2 files matching day", m) for m in messages)
    assert any(re.match(f"{run_prefix}reading day1.csv", m) for m in messages)


def test_python_m_runs_the_command():
    completed = subprocess.run(
        [sys.executable, "-m", "dagcraft", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == f"dagcraft {__version__}"
