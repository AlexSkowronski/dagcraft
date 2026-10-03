"""
The ``transform`` step: a list of operations applied to a table, in order.
"""

from typing import Any

from dagcraft.config.steps import TransformConfig
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.operations.chain import OperationCall, parse_operations, run_operations
from dagcraft.registry import register_step
from dagcraft.steps.base import BaseStep


@register_step("transform")
class TransformStep(BaseStep):
    """
    Applies ``operations`` to the ``data`` input, each to the last one's result.

    The operations are checked when the pipeline loads. Other inputs can be
    named in operations that take a table, such as a join's ``right``.
    """

    config_model = TransformConfig
    config: TransformConfig
    calls: list[OperationCall]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.calls = parse_operations(self.config.operations, set(self.config.inputs))

    def describe(self) -> str:
        return "transform: " + " -> ".join(call.operation.name for call in self.calls)

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        return run_operations(self.calls, inputs["data"], inputs)
