"""
``${run_date}``, and setting it and params from the command line.
"""

import logging
import sys
import types
from datetime import date

import pandas as pd
import pytest

from dagcraft import BaseStep, ConfigError, Pipeline, StepConfig, register_step
from dagcraft.cli import ExitCode, main


@register_step("run_date_recorder")
class RunDateStep(BaseStep):
    """
    Returns the run date its context gives.
    """

    config_model = StepConfig

    def execute(self, context, inputs):
        return context.run_date


@pytest.fixture
def day_files(tmp_path):
    """
    A CSV for two days, each naming its day.
    """
    for day in (date.today().isoformat(), "2026-10-17"):
        pd.DataFrame({"day": [day]}).to_csv(tmp_path / f"{day}.csv", index=False)


def read_day(**load):
    pipeline = Pipeline.from_dict(
        {
            "pipeline": {"name": "days"},
            "steps": [{"id": "day", "type": "read", "path": "${run_date}.csv"}],
        },
        **load,
    )
    return pipeline.run().output("day")["day"].tolist()


@pytest.mark.usefixtures("day_files")
def test_the_run_date_is_today_unless_set():
    assert read_day() == [date.today().isoformat()]


@pytest.mark.usefixtures("day_files")
@pytest.mark.parametrize("run_date", ["2026-10-17", date(2026, 10, 17)])
def test_the_run_date_can_be_set_when_loading(run_date):
    assert read_day(run_date=run_date) == ["2026-10-17"]


def test_a_whole_value_is_a_date(monkeypatch):
    module = types.ModuleType("dagcraft_test_run_date")
    monkeypatch.setattr(module, "echo", lambda day: day, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    pipeline = Pipeline.from_dict(
        {
            "pipeline": {"name": "days"},
            "steps": [
                {
                    "id": "echo",
                    "type": "python",
                    "callable": "dagcraft_test_run_date:echo",
                    "args": {"day": "${run_date}"},
                }
            ],
        },
        run_date="2026-10-17",
    )

    assert pipeline.run().output("echo") == date(2026, 10, 17)


def test_params_can_use_the_run_date():
    pipeline = Pipeline.from_dict(
        {
            "pipeline": {"name": "days"},
            "params": {"folder": "raw/${run_date}"},
            "steps": [{"id": "day", "type": "read", "path": "${params.folder}/x.csv"}],
        },
        run_date="2026-10-17",
    )

    assert pipeline.params == {"folder": "raw/2026-10-17"}


def test_steps_of_your_own_get_the_run_date():
    pipeline = Pipeline.from_dict(
        {
            "pipeline": {"name": "days"},
            "steps": [{"id": "day", "type": "run_date_recorder"}],
        },
        run_date="2026-10-17",
    )

    assert pipeline.run_date == date(2026, 10, 17)
    assert pipeline.run().output("day") == date(2026, 10, 17)


def test_a_run_date_that_isnt_a_date_says_so():
    with pytest.raises(ConfigError, match="Run date 'yesterday' isn't a date"):
        read_day(run_date="yesterday")


def test_dates_written_in_the_file_can_be_used_inside_text(tmp_path):
    pd.DataFrame({"n": [1]}).to_csv(tmp_path / "orders_2026-10-02.csv", index=False)
    (tmp_path / "pipeline.yaml").write_text(
        """
pipeline: {name: days}
params:
  day: 2026-10-02
steps:
  - {id: orders, type: read, path: 'orders_${params.day}.csv'}
""",
        encoding="utf-8",
    )

    result = Pipeline.from_yaml("pipeline.yaml").run()

    assert result.output("orders")["n"].tolist() == [1]


@pytest.fixture
def regions(tmp_path):
    """
    A pipeline that copies a region's file for the run date, keeping some columns.
    """
    (tmp_path / "south").mkdir()
    pd.DataFrame({"a": [1], "b": [2], "c": [3]}).to_csv(
        tmp_path / "south" / "2026-10-17.csv", index=False
    )
    (tmp_path / "pipeline.yaml").write_text(
        """
pipeline: {name: regions}
params:
  region: north
  columns: [a]
steps:
  - id: sales
    type: read
    path: ${params.region}/${run_date}.csv
  - id: some
    type: transform
    inputs: {data: sales}
    operations:
      - select: ${params.columns}
  - id: save
    type: write
    path: out.csv
    inputs: {data: some}
""",
        encoding="utf-8",
    )
    return tmp_path


def test_the_command_sets_params_and_the_run_date(regions):
    code = main(
        [
            "pipeline.yaml",
            "--run-date",
            "2026-10-17",
            "--param",
            "region=south",
            "--param",
            "columns=[a, c]",  # read as YAML: a list
        ]
    )

    assert code == ExitCode.SUCCESS
    assert pd.read_csv(regions / "out.csv").columns.tolist() == ["a", "c"]


@pytest.mark.usefixtures("regions")
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ["--param", "colour=red"],
            "Unknown parameter: colour. Defined: region, columns.",
        ),
        (["--run-date", "17/10/2026"], "Run date '17/10/2026' isn't a date"),
    ],
)
def test_the_command_rejects_unknown_params_and_bad_dates(arguments, message, caplog):
    with caplog.at_level(logging.ERROR):
        assert main(["pipeline.yaml", *arguments]) == ExitCode.INVALID

    assert message in caplog.text


@pytest.mark.parametrize("argument", ["region", "=south", "region=[a"])
def test_a_param_must_be_name_equals_value(argument, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["pipeline.yaml", "--param", argument])

    assert exc_info.value.code == ExitCode.INVALID
    assert "--param" in capsys.readouterr().err
