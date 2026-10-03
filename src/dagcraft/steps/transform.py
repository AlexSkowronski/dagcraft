"""The ``transform`` step: apply a registered operation to its inputs."""

from collections.abc import Callable
from typing import Any

from dagcraft.config.steps import TransformConfig
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.registry import OPERATIONS, register_step
from dagcraft.steps.base import BaseStep


@register_step("transform")
class TransformStep(BaseStep):
    """Calls ``operation`` with the inputs, by name, plus ``args``."""

    config_model = TransformConfig
    config: TransformConfig
    function: Callable[..., Any]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.function = OPERATIONS.get(self.config.operation)

    def describe(self) -> str:
        return f"transform with '{self.config.operation}'"

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        return self.function(**inputs, **self.config.args)
