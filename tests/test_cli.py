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
    inputs:
      data: source
    operations:
      - sort: {{by: value, ascending: false}}
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
    inputs:
      data: source
    operations:
      - sort: value
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
    inputs: {{data: source}}
    operations: [{{sort: value}}]
""",
    )

    with caplog.at_level(logging.INFO):
        assert main([str(pipeline), "--dry-run"]) == ExitCode.SUCCESS

    assert report_lines(caplog) == [
        "Pipeline 'demo' is valid.",
        "Params: limit=2",
        "Steps, in run order:",
        f"  1. source  read {input_csv.as_posix()} from 'local'",
        "  2. sorted  transform: sort  <- data: source",
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


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ["--max-workers", "0"],
            "max_workers: Input should be greater than or equal to 1",
        ),
        (["--run-id", ""], "run_id: String should have at least 1 character"),
    ],
)
def test_invalid_options_exit_2_before_loading(tmp_path, caplog, arguments, message):
    missing = str(tmp_path / "nowhere.yaml")

    assert main([missing, *arguments]) == ExitCode.INVALID
    assert f"Invalid run options: {message}" in caplog.text
    # Checked before the file is read.
    assert "Could not read pipeline file" not in caplog.text


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


@pytest.fixture
def isolated_imports(monkeypatch):
    """
    Undo changes to the import path and forget the test's module afterwards.
    """
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    sys.modules.pop("dagcraft_project_functions", None)


@pytest.mark.usefixtures("isolated_imports")
def test_python_steps_import_your_modules_from_where_you_run(tmp_path):
    # Tests run from tmp_path, which, like the dagcraft command's own
    # launcher, isn't on the import path to begin with.
    assert str(tmp_path) not in sys.path
    (tmp_path / "dagcraft_project_functions.py").write_text(
        "def summarise():\n    return {'countries': ['GB', 'PL']}\n",
        encoding="utf-8",
    )
    pipeline = write_pipeline(
        tmp_path,
        """
pipeline:
  name: demo
steps:
  - id: summary
    type: python
    callable: dagcraft_project_functions:summarise
  - id: save
    type: write
    path: out/summary.json
    inputs: {data: summary}
""",
    )

    assert main([str(pipeline)]) == ExitCode.SUCCESS
    assert (tmp_path / "out" / "summary.json").read_text(encoding="utf-8") == (
        '{"countries": ["GB", "PL"]}'
    )


def test_python_m_runs_the_command():
    completed = subprocess.run(
        [sys.executable, "-m", "dagcraft", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == f"dagcraft {__version__}"
