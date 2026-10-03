"""The ``write`` step: put data somewhere through a connection."""

from typing import Any

from dagcraft.config.steps import WriteConfig, extra_fields
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.registry import WRITERS, register_step
from dagcraft.steps.base import BaseStep
from dagcraft.steps.connections import find_connection, prepare_handler
from dagcraft.writers import Writer


@register_step("write")
class WriteStep(BaseStep):
    """Writes with the writer registered for the connection's type.

    Several inputs are written together (as Excel sheets, say) when the
    writer accepts them; the step's output is what it wrote.
    """

    config_model = WriteConfig
    config: WriteConfig
    writer: Writer

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)
        self.writer = prepare_handler(
            WRITERS, connection, extra_fields(self.config), "writing"
        )

        if len(self.config.inputs) > 1 and not self.writer.accepts_multiple_inputs():
            raise ValueError(
                "Only formats that hold several tables, such as excel (one "
                "sheet per input), can write several inputs."
            )

    def describe(self) -> str:
        target = self.writer.describe()
        return f"write{f' {target}' if target else ''} to '{self.config.connection}'"

    def connection_name(self) -> str:
        return self.config.connection

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        # Several inputs are passed on by name, e.g. as Excel sheets.
        data = next(iter(inputs.values())) if len(inputs) == 1 else dict(inputs)
        self.writer.write(context.connection(self.config.connection), data)
        return data
