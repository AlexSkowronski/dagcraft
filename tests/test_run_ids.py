import logging
import re

import pytest

from dagcraft import BaseStep, Pipeline, RunError, StepConfig, register_step
from dagcraft.cli import main


@register_step("chatty")
class ChattyStep(BaseStep):
    """
    Logs through the run's logger, as steps and connections can.
    """

    config_model = StepConfig

    def execute(self, context, inputs):
        context.logger.info("hello from inside the step")
        return 1


def make_pipeline(*steps):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "ids"},
            "steps": list(steps or [{"id": "a", "type": "chatty"}]),
        }
    )


def dagcraft_records(caplog):
    return [record for record in caplog.records if record.name.startswith("dagcraft")]


def test_each_run_gets_a_short_random_id():
    pipeline = make_pipeline()

    first, second = pipeline.run().run_id, pipeline.run().run_id

    assert re.fullmatch(r"[0-9a-f]{8}", first)
    assert first != second


def test_logs_carry_the_pipeline_and_run_id(caplog):
    with caplog.at_level(logging.INFO, logger="dagcraft"):
        result = make_pipeline().run(run_id="adf-1234")

    assert result.run_id == "adf-1234"

    records = dagcraft_records(caplog)
    assert [record.getMessage() for record in records] == [
        "[ids adf-1234] Starting run: 1 step",
        "[ids adf-1234] a: started: chatty",
        "[ids adf-1234] a: hello from inside the step",
        f"[ids adf-1234] a: finished in {result.steps['a'].duration:.3f}s: int",
        f"[ids adf-1234] Run succeeded in {result.duration:.3f}s",
    ]
    assert {(record.pipeline, record.run_id) for record in records} == {
        ("ids", "adf-1234")
    }
    assert [record.step for record in records] == ["", "a", "a", "a", ""]


def test_failed_run_keeps_its_id():
    pipeline = make_pipeline(
        {"id": "missing", "type": "read", "path": "does_not_exist.csv"},
    )

    with pytest.raises(RunError) as exc_info:
        pipeline.run(run_id="nightly-7")

    assert exc_info.value.result.run_id == "nightly-7"


def test_cli_run_id(tmp_path, caplog):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        "pipeline: {name: cli}\nsteps:\n  - {id: a, type: chatty}\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        main([str(path), "--run-id", "from-adf"])

    assert "[cli from-adf] a: hello from inside the step" in caplog.text
