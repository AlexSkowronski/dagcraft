"""The dependency graph between steps, and the order they run in."""

import heapq
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from dagcraft.exceptions import GraphError


@dataclass(frozen=True)
class CompiledGraph:
    """Each step's dependencies, and an order that respects them."""

    dependencies: dict[str, set[str]]
    order: list[str]


def compile_graph(dependencies: dict[str, set[str]]) -> CompiledGraph:
    """Check and order the graph.

    ``dependencies`` maps each step id, in declared order, to the ids of the
    steps it takes inputs from. Raises ``GraphError`` for unknown steps,
    self-dependencies and cycles.
    """
    for step_id, upstream_ids in dependencies.items():
        unknown = upstream_ids - dependencies.keys()

        if unknown:
            names = ", ".join(sorted(unknown))
            raise GraphError(
                f"Step '{step_id}' references unknown dependencies: {names}"
            )

        if step_id in upstream_ids:
            raise GraphError(f"Step '{step_id}' cannot depend on itself.")

    return CompiledGraph(
        dependencies=dependencies,
        order=topological_sort(dependencies),
    )


def topological_sort(dependencies: dict[str, set[str]]) -> list[str]:
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
