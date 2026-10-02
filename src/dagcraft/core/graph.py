from __future__ import annotations

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

    Steps that could run at the same point keep the order they're declared in.
    """
    sorter: TopologicalSorter[str] = TopologicalSorter()

    # Adding every step before any dependency fixes the tie-breaking order.
    for node in dependencies:
        sorter.add(node)

    for node, deps in dependencies.items():
        sorter.add(node, *deps)

    try:
        return list(sorter.static_order())
    except CycleError as exc:
        cycle = " -> ".join(exc.args[1])
        raise GraphError(f"Cycle detected in pipeline DAG: {cycle}") from None
