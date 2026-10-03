"""Opening connections when a run first needs them, and closing them after."""

import threading

from dagcraft.connections import Connection
from dagcraft.logs import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """A run's connections: each opened on first use, all closed at the end.

    Connections no step asks for are never opened. Safe to use from steps
    running in parallel.
    """

    def __init__(self, connections: dict[str, Connection]) -> None:
        self._connections = connections
        self._opened: list[Connection] = []
        self._lock = threading.Lock()

    def get(self, name: str) -> Connection:
        """The connection called ``name``, opened if this is its first use."""
        connection = self._connections[name]

        with self._lock:
            if connection not in self._opened:
                connection.open()
                self._opened.append(connection)

        return connection

    def close_all(self) -> None:
        """Close every connection opened so far, newest first.

        A connection that fails to close is logged, and the rest still close.
        """
        with self._lock:
            while self._opened:
                connection = self._opened.pop()

                try:
                    connection.close()
                except Exception:
                    logger.exception("Failed to close connection '%s'", connection.name)
