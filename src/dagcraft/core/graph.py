from __future__ import annotations

import heapq
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from dagcraft.exceptions import GraphError
from dagcraft.steps.base import StepConfig


@dataclass(frozen=True)
class CompiledGraph:
    dependencies: dict[str, set[str]]
    order: list[str]


def compile_graph(steps: list[StepConfig]) -> CompiledGraph:
    step_ids = {step.id for step in steps}

    dependencies: dict[str, set[str]] = {}

    for step in steps:
        deps = set(step.inputs.values())

        unknown = deps - step_ids

        if unknown:
            names = ", ".join(sorted(unknown))

            raise GraphError(
                f"Step '{step.id}' references unknown dependencies: {names}"
            )

        if step.id in deps:
            raise GraphError(f"Step '{step.id}' cannot depend on itself.")

        dependencies[step.id] = deps

    order = topological_sort(dependencies)

    return CompiledGraph(
        dependencies=dependencies,
        order=order,
    )


def topological_sort(
    dependencies: dict[str, set[str]],
) -> list[str]:
    """Order steps so each comes after the steps it depends on.

    Whenever several steps are ready, the one declared first goes next, so
    steps run in the order they're written unless a dependency says
    otherwise.
    """
    position = {node: index for index, node in enumerate(dependencies)}
    sorter: TopologicalSorter[str] = TopologicalSorter(dependencies)

    try:
        sorter.prepare()
    except CycleError as exc:
        cycle = " -> ".join(exc.args[1])
        raise GraphError(f"Cycle detected in pipeline DAG: {cycle}") from None

    ready: list[tuple[int, str]] = []
    order: list[str] = []

    while sorter.is_active():
        for node in sorter.get_ready():
            heapq.heappush(ready, (position[node], node))

        _, node = heapq.heappop(ready)
        order.append(node)
        sorter.done(node)

    return order
