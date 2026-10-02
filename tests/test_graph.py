import pytest

from dagcraft.core.graph import compile_graph, topological_sort
from dagcraft.exceptions import GraphError
from dagcraft.steps.base import StepConfig


def compile_steps(*steps):
    return compile_graph([StepConfig.model_validate(step) for step in steps])


def read(step_id):
    return {"id": step_id, "type": "read"}


def transform(step_id, **inputs):
    return {"id": step_id, "type": "transform", "inputs": inputs}


def test_dependencies_come_before_dependents():
    # Declared out of order on purpose.
    graph = compile_steps(
        transform("joined", left="a", right="b"),
        read("a"),
        read("b"),
    )

    order = graph.order
    assert order.index("a") < order.index("joined")
    assert order.index("b") < order.index("joined")
    assert graph.dependencies["joined"] == {"a", "b"}


def test_order_follows_declaration_for_independent_steps():
    graph = compile_steps(read("c"), read("a"), read("b"))

    assert graph.order == ["c", "a", "b"]


def test_unknown_dependency():
    with pytest.raises(
        GraphError,
        match="references unknown dependencies: missing",
    ):
        compile_steps(transform("t", data="missing"))


def test_self_dependency():
    with pytest.raises(GraphError, match="cannot depend on itself"):
        compile_steps(transform("t", data="t"))


def test_cycle_detected():
    with pytest.raises(GraphError, match="Cycle detected"):
        compile_steps(
            transform("a", data="b"),
            transform("b", data="a"),
        )


def test_topological_sort_diamond():
    order = topological_sort(
        {
            "src": set(),
            "left": {"src"},
            "right": {"src"},
            "sink": {"left", "right"},
        }
    )

    assert order[0] == "src"
    assert order[-1] == "sink"
    assert set(order) == {"src", "left", "right", "sink"}
