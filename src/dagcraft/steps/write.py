from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from dagcraft.registry import register_step
from dagcraft.steps.base import BaseStep, StepConfig, find_connection

if TYPE_CHECKING:
    from dagcraft.connections import Connection
    from dagcraft.core.runtime import ExecutionContext


class WriteConfig(StepConfig):
    """Fields beyond these are defined by the connection's type."""

    model_config = ConfigDict(extra="allow")

    connection: str = "local"

    @model_validator(mode="after")
    def check_one_input(self) -> Self:
        if len(self.inputs) != 1:
            raise ValueError("A write step needs exactly one input.")
        return self


@register_step("write")
class WriteStep(BaseStep):
    config_model = WriteConfig
    config: WriteConfig
    options: BaseModel

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)

        if connection.write_options is None:
            raise ValueError(
                f"Connection '{connection.name}' does not support writing."
            )

        self.options = connection.write_options.model_validate(
            self.config.model_extra or {}
        )

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        (data,) = inputs.values()

        connection = context.connection(self.config.connection)
        connection.write(data, self.options)

        return data
