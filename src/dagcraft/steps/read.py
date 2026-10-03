"""
The ``read`` step: fetch data through a connection.
"""

from typing import Any

from dagcraft.config.steps import ReadConfig, extra_fields
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.data import is_empty
from dagcraft.exceptions import ExecutionError, NothingFound
from dagcraft.logs import get_logger
from dagcraft.readers import Reader
from dagcraft.registry import READERS, register_step
from dagcraft.steps.base import BaseStep
from dagcraft.steps.connections import find_connection, prepare_handler

logger = get_logger(__name__)


@register_step("read")
class ReadStep(BaseStep):
    """
    Reads with the reader registered for the connection's type.

    The files to read can come from another step, as a ``paths`` input.
    Finding nothing (no rows, no files) fails the step, unless ``if_empty``
    says to ``stop`` or ``continue``; it's never quiet.
    """

    config_model = ReadConfig
    config: ReadConfig
    reader: Reader

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)
        self.reader = prepare_handler(
            READERS, connection, extra_fields(self.config), "reading"
        )
        self.reader.expect_paths(self.lister is not None)

    @property
    def lister(self) -> str | None:
        """
        The step whose output lists the files to read, if any.
        """
        return self.config.inputs.get("paths")

    def describe(self) -> str:
        if self.lister is not None:
            target = f"the files '{self.lister}' lists"
        else:
            target = self.reader.describe()
        return f"read{f' {target}' if target else ''} from '{self.config.connection}'"

    def connection_name(self) -> str:
        return self.config.connection

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        connection = context.connection(self.config.connection)

        if self.lister is None:
            data = self.reader.read(connection)
            where = f"{self.reader.describe()} from '{self.config.connection}'"
        elif is_empty(inputs["paths"]):
            data = self.reader.read_listed(connection, inputs["paths"])
            where = f"the files '{self.lister}' lists: it listed none"
        else:
            data = self.reader.read_listed(connection, inputs["paths"])
            where = f"the files '{self.lister}' lists"

        return self.found_nothing(data, where) if is_empty(data) else data

    def found_nothing(self, data: Any, where: str) -> Any:
        """
        Fail, stop or carry on, as ``if_empty`` says; never quietly.
        """
        if self.config.if_empty == "stop":
            raise NothingFound(where)

        if self.config.if_empty == "continue":
            logger.warning("found nothing in %s; carrying on", where)
            return data

        raise ExecutionError(
            f"Found nothing in {where}. If that can happen, set if_empty to "
            "stop (skip the steps that need it) or continue."
        )
