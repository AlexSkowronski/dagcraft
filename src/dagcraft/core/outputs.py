"""Holding step outputs during a run, and letting go of them when done."""

import threading
from typing import Any

from dagcraft.core.graph import CompiledGraph


class OutputStore:
    """The outputs of finished steps, which later steps take as inputs.

    With ``keep`` false, an output is dropped as soon as every step that
    takes it as an input has finished, so memory only holds what's still
    needed. With ``keep`` true, every output stays, for the run's result.
    """

    def __init__(self, graph: CompiledGraph, *, keep: bool) -> None:
        self._dependencies = graph.dependencies
        self._keep = keep
        self._values: dict[str, Any] = {}
        self._lock = threading.Lock()
        # How many steps still to finish take each step's output as an input.
        self._consumers = dict.fromkeys(graph.order, 0)

        for upstream_ids in graph.dependencies.values():
            for upstream in upstream_ids:
                self._consumers[upstream] += 1

    def put(self, step_id: str, value: Any) -> None:
        """Store what ``step_id`` returned."""
        with self._lock:
            self._values[step_id] = value

    def inputs_for(self, inputs: dict[str, str]) -> dict[str, Any]:
        """A step's input values by input name, from its ``inputs`` mapping."""
        with self._lock:
            return {name: self._values[step_id] for name, step_id in inputs.items()}

    def step_finished(self, step_id: str) -> None:
        """Note that ``step_id`` is done, dropping outputs nothing else needs."""
        if self._keep:
            return

        with self._lock:
            for upstream in self._dependencies[step_id]:
                self._consumers[upstream] -= 1

                if self._consumers[upstream] == 0:
                    self._values.pop(upstream, None)

            if self._consumers[step_id] == 0:
                self._values.pop(step_id, None)

    def names(self) -> list[str]:
        """The ids of the steps whose outputs are held, sorted."""
        with self._lock:
            return sorted(self._values)

    def as_dict(self) -> dict[str, Any]:
        """Every output still held, by step id."""
        with self._lock:
            return dict(self._values)
