import logging
import threading
import time
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from dagcraft import (
    BaseStep,
    ConfigError,
    Connection,
    Pipeline,
    PipelineError,
    StepConfig,
    register_connection,
    register_step,
)
from dagcraft.cli import main
from dagcraft.core.runtime import StepStatus


class TrackedConfig(StepConfig):
    meet: int = 0  # wait until this many tracked steps are running at once
    delay: float = 0  # then keep running this many seconds
    fail: bool = False
    connection: str | None = None


@register_step("tracked")
class TrackedStep(BaseStep):
    """Records when it runs and on which thread; optionally waits for others."""

    config_model = TrackedConfig
    config: TrackedConfig

    lock: ClassVar[threading.Lock] = threading.Lock()
    events: ClassVar[list[tuple[str, str]]] = []
    threads: ClassVar[dict[str, threading.Thread]] = {}
    active: ClassVar[int] = 0
    most_active: ClassVar[int] = 0
    barriers: ClassVar[dict[int, threading.Barrier]] = {}

    def execute(self, context, inputs):
        cls = type(self)
        with cls.lock:
            cls.events.append(("start", self.config.id))
            cls.threads[self.config.id] = threading.current_thread()
            cls.active += 1
            cls.most_active = max(cls.most_active, cls.active)

        try:
            if self.config.connection:
                context.connection(self.config.connection)
            if self.config.meet:
                cls.barriers[self.config.meet].wait(timeout=5)
            time.sleep(self.config.delay)
            if self.config.fail:
                raise RuntimeError("broken")
            return self.config.id
        finally:
            with cls.lock:
                cls.active -= 1
                cls.events.append(("end", self.config.id))


class SlowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


@register_connection("slow_open")
class SlowOpenConnection(Connection):
    config_model = SlowConfig
    opens: ClassVar[int] = 0

    def open(self) -> None:
        time.sleep(0.05)
        type(self).opens += 1


@pytest.fixture(autouse=True)
def reset():
    TrackedStep.events.clear()
    TrackedStep.threads.clear()
    TrackedStep.active = TrackedStep.most_active = 0
    TrackedStep.barriers = {2: threading.Barrier(2), 3: threading.Barrier(3)}
    SlowOpenConnection.opens = 0


def make_pipeline(*steps, max_workers=1, connections=None):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "parallel", "max_workers": max_workers},
            "connections": connections or {},
            "steps": list(steps),
        }
    )


def tracked(step_id, **fields):
    return {"id": step_id, "type": "tracked", **fields}


def test_independent_steps_run_at_the_same_time():
    # Each step waits until all three are running: only possible in parallel.
    result = make_pipeline(
        tracked("a", meet=3),
        tracked("b", meet=3),
        tracked("c", meet=3),
        max_workers=3,
    ).run()

    assert result.success
    assert TrackedStep.most_active == 3


def test_never_more_than_max_workers_at_once():
    result = make_pipeline(
        *(tracked(name, meet=2) for name in "abcd"),
        max_workers=2,
    ).run()

    assert result.success
    assert TrackedStep.most_active == 2


def test_steps_wait_for_their_inputs():
    make_pipeline(
        tracked("first"),
        tracked("second", inputs={"x": "first"}),
        tracked("other"),
        max_workers=3,
    ).run()

    events = TrackedStep.events
    assert events.index(("end", "first")) < events.index(("start", "second"))


def test_one_worker_runs_steps_in_the_calling_thread():
    make_pipeline(tracked("a"), tracked("b")).run()

    assert set(TrackedStep.threads.values()) == {threading.current_thread()}
    assert [event for event in TrackedStep.events if event[0] == "start"] == [
        ("start", "a"),
        ("start", "b"),
    ]


def test_failures_skip_dependents_and_others_still_run():
    with pytest.raises(PipelineError) as exc_info:
        make_pipeline(
            tracked("bad", fail=True),
            tracked("after_bad", inputs={"x": "bad"}),
            tracked("good"),
            tracked("after_good", inputs={"x": "good"}),
            max_workers=4,
        ).run()

    statuses = {
        step_id: step.status for step_id, step in exc_info.value.result.steps.items()
    }
    assert statuses == {
        "bad": StepStatus.FAILED,
        "after_bad": StepStatus.SKIPPED,
        "good": StepStatus.SUCCESS,
        "after_good": StepStatus.SUCCESS,
    }


def test_fail_fast_lets_running_steps_finish_and_skips_the_rest():
    with pytest.raises(PipelineError) as exc_info:
        make_pipeline(
            # Both start together; "waits" is still running when "bad" fails.
            tracked("bad", meet=2, fail=True),
            tracked("waits", meet=2, delay=0.2),
            tracked("later", inputs={"x": "waits"}),
            max_workers=2,
        ).run(fail_fast=True)

    steps = exc_info.value.result.steps
    assert steps["bad"].status == StepStatus.FAILED
    assert steps["waits"].status == StepStatus.SUCCESS
    assert steps["later"].status == StepStatus.SKIPPED


def test_shared_connection_is_opened_once():
    result = make_pipeline(
        *(tracked(name, connection="db") for name in "abc"),
        max_workers=3,
        connections={"db": {"type": "slow_open"}},
    ).run()

    assert result.success
    assert SlowOpenConnection.opens == 1


def test_run_overrides_the_files_max_workers():
    result = make_pipeline(
        tracked("a", meet=2),
        tracked("b", meet=2),
        max_workers=1,
    ).run(max_workers=2)

    assert result.success


def test_max_workers_is_validated():
    with pytest.raises(ConfigError, match="max_workers: Input should be greater"):
        make_pipeline(tracked("a"), max_workers=0)

    with pytest.raises(ValueError, match="max_workers must be at least 1"):
        make_pipeline(tracked("a")).run(max_workers=0)


def test_cli_max_workers(tmp_path, caplog):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        "pipeline: {name: cli}\n"
        "steps:\n"
        "  - {id: a, type: tracked, meet: 2}\n"
        "  - {id: b, type: tracked, meet: 2}\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        main(["run", str(path), "--max-workers", "2", "--dry-run"])
        main(["run", str(path), "--max-workers", "2"])

    assert "Up to 2 independent steps run at once." in caplog.text
    assert TrackedStep.most_active == 2
