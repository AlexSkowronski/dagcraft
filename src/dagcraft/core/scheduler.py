"""
Deciding which step runs next, and which steps to skip.
"""

import heapq

from dagcraft.core.graph import CompiledGraph
from dagcraft.core.results import StepStatus


class Scheduler:
    """
    Tracks which steps are ready to run as others finish.

    A step is ready once every step it depends on has finished; among ready
    steps, the one declared first goes next. A ready step should be skipped
    when a step it depends on didn't succeed, or, with ``fail_fast``, when
    any step has failed. The scheduler knows nothing about threads: the
    executor asks it what to start and tells it what finished.
    """

    def __init__(self, graph: CompiledGraph, *, fail_fast: bool) -> None:
        self._graph = graph
        self._fail_fast = fail_fast
        self._position = {step_id: index for index, step_id in enumerate(graph.order)}
        self._waiting = {
            step_id: len(graph.dependencies[step_id]) for step_id in graph.order
        }
        self._dependents: dict[str, list[str]] = {
            step_id: [] for step_id in graph.order
        }
        self._succeeded: set[str] = set()
        self._stopped = False

        for step_id in graph.order:
            for upstream in graph.dependencies[step_id]:
                self._dependents[upstream].append(step_id)

        self._ready = [
            (self._position[step_id], step_id)
            for step_id in graph.order
            if not self._waiting[step_id]
        ]

    def has_ready(self) -> bool:
        """
        Whether a step is waiting to be started or skipped.
        """
        return bool(self._ready)

    def pop_ready(self) -> str:
        """
        Take the earliest declared ready step.
        """
        return heapq.heappop(self._ready)[1]

    def skip_reason(self, step_id: str) -> str | None:
        """
        Why ``step_id`` shouldn't run, or ``None`` if it should.
        """
        if self._stopped:
            return "an earlier step failed and fail_fast is on"

        dependencies = self._graph.dependencies[step_id]

        for upstream in self._graph.order:
            if upstream in dependencies and upstream not in self._succeeded:
                return f"upstream step '{upstream}' did not succeed"
        return None

    def finished(self, step_id: str, status: StepStatus) -> None:
        """
        Record how ``step_id`` ended, readying the steps that waited on it.
        """
        if status == StepStatus.SUCCESS:
            self._succeeded.add(step_id)
        elif status == StepStatus.FAILED and self._fail_fast:
            self._stopped = True

        for dependent in self._dependents[step_id]:
            self._waiting[dependent] -= 1

            if not self._waiting[dependent]:
                heapq.heappush(self._ready, (self._position[dependent], dependent))

    def position(self, step_id: str) -> int:
        """
        Where ``step_id`` comes in run order, to sort steps that end together.
        """
        return self._position[step_id]
