from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import Field

from dagcraft.registry import OPERATIONS, register_step
from dagcraft.steps.base import BaseStep, FunctionStepConfig

if TYPE_CHECKING:
    from dagcraft.connections import Connection
    from dagcraft.core.runtime import ExecutionContext


class TransformConfig(FunctionStepConfig):
    operation: str = Field(min_length=1)


@register_step("transform")
class TransformStep(BaseStep):
    config_model = TransformConfig
    config: TransformConfig
    function: Callable[..., Any]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.function = OPERATIONS.get(self.config.operation)

    def describe(self) -> str:
        return f"transform with '{self.config.operation}'"

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        return self.function(
            **inputs,
            **self.config.args,
        )
