from dagcraft import StepStatus
from dagcraft.core.graph import compile_graph
from dagcraft.core.outputs import OutputStore
from dagcraft.core.scheduler import Scheduler

# a and b are independent; c takes both; d takes c.
GRAPH = compile_graph({"a": set(), "b": set(), "c": {"a", "b"}, "d": {"c"}})


def drain(scheduler):
    """
    Pop every ready step.
    """
    ready = []
    while scheduler.has_ready():
        ready.append(scheduler.pop_ready())
    return ready


def test_steps_become_ready_as_their_inputs_finish():
    scheduler = Scheduler(GRAPH, fail_fast=False)

    assert drain(scheduler) == ["a", "b"]

    scheduler.finished("a", StepStatus.SUCCESS)
    assert not scheduler.has_ready()

    scheduler.finished("b", StepStatus.SUCCESS)
    assert drain(scheduler) == ["c"]
    assert scheduler.skip_reason("c") is None


def test_a_failed_input_means_skipping():
    scheduler = Scheduler(GRAPH, fail_fast=False)
    drain(scheduler)

    scheduler.finished("a", StepStatus.FAILED)
    scheduler.finished("b", StepStatus.SUCCESS)

    assert drain(scheduler) == ["c"]
    assert scheduler.skip_reason("c") == "upstream step 'a' did not succeed"


def test_fail_fast_skips_everything_after_a_failure():
    scheduler = Scheduler(GRAPH, fail_fast=True)
    drain(scheduler)

    scheduler.finished("a", StepStatus.FAILED)

    assert scheduler.skip_reason("b") == "an earlier step failed and fail_fast is on"


def test_outputs_are_released_once_their_consumers_finish():
    outputs = OutputStore(GRAPH, keep=False)
    for step_id in ("a", "b"):
        outputs.put(step_id, step_id.upper())
        outputs.step_finished(step_id)

    inputs = outputs.inputs_for({"left": "a", "right": "b"})
    assert inputs == {"left": "A", "right": "B"}

    outputs.put("c", "C")
    outputs.step_finished("c")
    assert outputs.names() == ["c"]

    outputs.put("d", "D")
    outputs.step_finished("d")
    assert outputs.names() == []


def test_outputs_are_all_kept_when_asked():
    outputs = OutputStore(GRAPH, keep=True)
    for step_id in ("a", "b", "c", "d"):
        outputs.put(step_id, step_id)
        outputs.step_finished(step_id)

    assert outputs.as_dict() == {"a": "a", "b": "b", "c": "c", "d": "d"}
