from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from dagcraft.config import PipelineConfig
from dagcraft.exceptions import GraphError


@dataclass(frozen=True)
class CompiledGraph:
    dependencies: dict[str, set[str]]
    order: list[str]


def compile_graph(config: PipelineConfig) -> CompiledGraph:
    step_ids = {step.id for step in config.steps}

    dependencies: dict[str, set[str]] = {}

    for step in config.steps:
        deps = set(step.inputs.values())

        unknown = deps - step_ids

        if unknown:
            names = ", ".join(sorted(unknown))

            raise GraphError(
                f"Step '{step.id}' references unknown dependencies: {names}"
            )

        if step.id in deps:
            raise GraphError(
                f"Step '{step.id}' cannot depend on itself."
            )

        dependencies[step.id] = deps

    order = topological_sort(dependencies)

    return CompiledGraph(
        dependencies=dependencies,
        order=order,
    )


def topological_sort(
    dependencies: dict[str, set[str]],
) -> list[str]:
    remaining = {
        node: set(deps)
        for node, deps in dependencies.items()
    }

    ready = deque(
        node
        for node, deps in remaining.items()
        if not deps
    )

    result: list[str] = []

    while ready:
        node = ready.popleft()

        if node in result:
            continue

        result.append(node)

        for candidate, deps in remaining.items():
            if node not in deps:
                continue

            deps.remove(node)

            if not deps and candidate not in result:
                ready.append(candidate)

    if len(result) != len(dependencies):
        unresolved = [
            node
            for node in dependencies
            if node not in result
        ]

        raise GraphError(
            "Cycle detected in pipeline DAG. "
            f"Unresolved nodes: {', '.join(unresolved)}"
        )

    return result