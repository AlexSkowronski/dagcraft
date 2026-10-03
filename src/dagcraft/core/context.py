"""
What a running step can reach.
"""

from dataclasses import dataclass, field
from typing import Any

from dagcraft.connections import Connection
from dagcraft.core.connection_manager import ConnectionManager
from dagcraft.core.outputs import OutputStore
from dagcraft.logs import RunLogger, get_logger


@dataclass
class ExecutionContext:
    """
    Passed to every step's ``execute``: the run's connections, params and more.

    ``logger`` logs with the run and step in each message, for steps of your
    own; ``dagcraft.get_logger(__name__)`` does the same from any module.
    """

    run_id: str
    params: dict[str, Any]
    connections: ConnectionManager
    outputs: OutputStore
    logger: RunLogger = field(default_factory=lambda: get_logger("dagcraft.steps"))

    def connection(self, name: str) -> Connection:
        """
        The connection called ``name``, opened on first use in this run.
        """
        return self.connections.get(name)
