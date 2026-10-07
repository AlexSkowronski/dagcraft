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


@register_step("after_recorder")
class RecorderStep(BaseStep):
    """
    Notes when it runs, and which outputs are still held.
    """

    config_model = StepConfig
    order: ClassVar[list[str]] = []
    held: ClassVar[dict[str, list[str]]] = {}

    def execute(self, context, inputs):
        self.order.append(self.config.id)
        self.held[self.config.id] = context.outputs.names()
        return self.config.id


@register_step("after_failure")
class FailureStep(BaseStep):
    config_model = StepConfig

    def execute(self, context, inputs):
        raise RuntimeError("no")


@pytest.fixture(autouse=True)
def clear():
    RecorderStep.order.clear()
    RecorderStep.held.clear()


def make(*steps, max_workers=4):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "after", "max_workers": max_workers},
            "steps": list(steps),
        }
    )


def step(step_id, kind="after_recorder", **fields):
    return {"id": step_id, "type": kind, **fields}


def test_a_step_waits_for_the_steps_it_is_after():
    # Declared first and free to start at once, but it must wait.
    make(
        step("read_back", after=["load"]),
        step("load", after=["seed"]),
        step("seed"),
    ).run()

    assert RecorderStep.order == ["seed", "load", "read_back"]


def test_it_is_skipped_if_one_of_them_fails(caplog):
    with (
        caplog.at_level(logging.WARNING, logger="dagcraft"),
        pytest.raises(RunError) as exc_info,
    ):
        make(step("load", "after_failure"), step("read_back", after=["load"])).run()

    steps = exc_info.value.result.steps
    assert steps["read_back"].status == StepStatus.SKIPPED
    assert "read_back: skipped: upstream step 'load' did not succeed" in caplog.text


def test_outputs_are_not_kept_for_steps_that_are_only_after_them():
    make(
        step("load"),
        step("read_back", after=["load"]),
        max_workers=1,
    ).run(keep_outputs=False)

    # load's output had no step taking it, so it was already dropped.
    assert RecorderStep.held["read_back"] == []


def test_the_plan_shows_what_a_step_is_after():
    plan = make(step("load"), step("read_back", after=["load"])).plan()

    assert plan[1].after == ["load"]


def test_after_must_name_a_step():
    with pytest.raises(ConfigError, match="references unknown dependencies: lod"):
        make(step("load"), step("read_back", after=["lod"]))
