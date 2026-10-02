from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from dagcraft.registry import register_step
from dagcraft.steps.base import BaseStep, StepConfig, find_connection

if TYPE_CHECKING:
    from dagcraft.connections import Connection
    from dagcraft.core.runtime import ExecutionContext


class ReadConfig(StepConfig):
    """Fields beyond these are defined by the connection's type."""

    model_config = ConfigDict(extra="allow")

    connection: str = "local"

    @model_validator(mode="after")
    def check_no_inputs(self) -> Self:
        if self.inputs:
            raise ValueError("A read step cannot have inputs.")
        return self


@register_step("read")
class ReadStep(BaseStep):
    config_model = ReadConfig
    config: ReadConfig
    options: BaseModel
    target: str

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)

        if connection.read_options is None:
            raise ValueError(
                f"Connection '{connection.name}' does not support reading."
            )

        self.options = connection.prepare_read(
            connection.read_options.model_validate(self.config.model_extra or {})
        )
        self.target = connection.describe(self.options)

    def describe(self) -> str:
        target = f" {self.target}" if self.target else ""
        return f"read{target} from '{self.config.connection}'"

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        connection = context.connection(self.config.connection)

        return connection.read(self.options)
