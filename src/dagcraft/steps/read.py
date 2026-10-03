"""
The ``read`` step: fetch data through a connection.
"""

from typing import Any

from dagcraft.config.steps import ReadConfig, extra_fields
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.readers import Reader
from dagcraft.registry import READERS, register_step
from dagcraft.steps.base import BaseStep
from dagcraft.steps.connections import find_connection, prepare_handler


@register_step("read")
class ReadStep(BaseStep):
    """
    Reads with the reader registered for the connection's type.
    """

    config_model = ReadConfig
    config: ReadConfig
    reader: Reader

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)
        self.reader = prepare_handler(
            READERS, connection, extra_fields(self.config), "reading"
        )

    def describe(self) -> str:
        target = self.reader.describe()
        return f"read{f' {target}' if target else ''} from '{self.config.connection}'"

    def connection_name(self) -> str:
        return self.config.connection

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        return self.reader.read(context.connection(self.config.connection))
