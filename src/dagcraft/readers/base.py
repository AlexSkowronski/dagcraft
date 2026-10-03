"""
The base class for readers: what a read step fetches from a connection.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel


class Reader(ABC):
    """
    Fetches a table from one kind of connection, as a read step's fields say.

    Register a reader for a connection type with ``register_reader``; read
    steps on connections of that type (or a subclass) then use it.
    ``options_model`` validates the step's own fields (``path``, ``query``
    and so on). ``prepare`` runs when the pipeline compiles, so problems
    show up before anything runs; ``read`` runs during the run, with the
    connection open. A reader that ``accepts_paths`` can also read the files
    another step lists, with ``read_listed``.
    """

    options_model: ClassVar[type[BaseModel]]
    accepts_paths: ClassVar[bool] = False

    def __init__(self, options: Any) -> None:
        self.options = options

    def prepare(self, connection: Any) -> None:  # noqa: B027 - optional hook
        """
        Check the options against the connection. Raise ``ValueError``.
        """

    def expect_paths(self, listed: bool) -> None:
        """
        Check the options suit having a ``paths`` input (``listed``) or not.

        Raises ``ValueError``. Only readers that ``accepts_paths`` can read
        files another step lists.
        """
        if listed and not self.accepts_paths:
            raise ValueError(
                "This connection doesn't read files, so the step can't take a "
                "'paths' input."
            )

    def describe(self) -> str:
        """
        What is read, for dry runs and logs, such as ``table dbo.orders``.
        """
        return ""

    @abstractmethod
    def read(self, connection: Any) -> Any:
        """
        Read from the open ``connection`` and return the data.
        """

    def read_listed(self, connection: Any, listed: Any) -> Any:
        """
        Read the files another step ``listed``; for readers that ``accepts_paths``.
        """
        raise NotImplementedError
