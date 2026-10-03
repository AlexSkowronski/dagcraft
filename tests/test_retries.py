import logging
from typing import ClassVar

import pytest

from dagcraft import (
    BaseStep,
    ConfigError,
    Pipeline,
    RunError,
    StepConfig,
    StepStatus,
    register_step,
)
from dagcraft.core import step_runner


class FlakyConfig(StepConfig):
    failures: int


@register_step("flaky")
class FlakyStep(BaseStep):
    """Fails ``failures`` times, then succeeds."""

    config_model = FlakyConfig
    config: FlakyConfig
    calls: ClassVar[dict[str, int]] = {}

    def execute(self, context, inputs):
        calls = self.calls.get(self.config.id, 0) + 1
        self.calls[self.config.id] = calls

        if calls <= self.config.failures:
            raise ConnectionError(f"blip {calls}")
        return calls


@pytest.fixture(autouse=True)
def reset_and_record_sleeps(monkeypatch):
    FlakyStep.calls.clear()
    sleeps: list[float] = []
    monkeypatch.setattr(step_runner.time, "sleep", sleeps.append)
    return sleeps


def make_pipeline(**step):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "steps": [{"id": "flaky", "type": "flaky", **step}],
        }
    )


def test_retries_until_the_step_succeeds(reset_and_record_sleeps, caplog):
    with caplog.at_level(logging.WARNING, logger="dagcraft"):
        result = make_pipeline(failures=2, retries=3, retry_delay=1).run()

    step = result.steps["flaky"]
    assert (step.status, step.attempts) == (StepStatus.SUCCESS, 3)
    assert result.output("flaky") == 3
    assert reset_and_record_sleeps == [1, 2]
    assert "flaky: failed (attempt 1 of 4), retrying in 1.0s: blip 1" in caplog.text


def test_gives_up_after_the_last_retry(reset_and_record_sleeps, caplog):
    with (
        caplog.at_level(logging.ERROR, logger="dagcraft"),
        pytest.raises(RunError) as exc_info,
    ):
        make_pipeline(failures=10, retries=3, retry_delay=0.5).run()

    step = exc_info.value.result.steps["flaky"]
    assert (step.status, step.attempts, step.error) == (StepStatus.FAILED, 4, "blip 4")
    assert reset_and_record_sleeps == [0.5, 1.0, 2.0]
    assert "flaky: failed after 4 attempts" in caplog.text


def test_no_retries_by_default(reset_and_record_sleeps):
    with pytest.raises(RunError) as exc_info:
        make_pipeline(failures=1).run()

    assert exc_info.value.result.steps["flaky"].attempts == 1
    assert reset_and_record_sleeps == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"retries": -1}, "retries: Input should be greater than or equal to 0"),
        (
            {"retry_delay": -2},
            "retry_delay: Input should be greater than or equal to 0",
        ),
    ],
)
def test_retry_settings_are_validated(fields, message):
    with pytest.raises(ConfigError, match=message):
        make_pipeline(failures=0, **fields)
