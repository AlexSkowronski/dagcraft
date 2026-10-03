"""
The base class every connection type extends.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from dagcraft.exceptions import ExecutionError


class Connection(ABC):
    """
    Where data lives, and how to sign in to it.

    A connection holds a client (a filesystem, an HTTP session, a database
    engine) and nothing about what to read or write: that is up to the
    reader and writer registered for its kind of connection. It is created
    when the pipeline compiles, opened the first time a step uses it during a
    run, and closed when the run ends.

    Subclasses set ``config_model`` to validate their entry in the
    ``connections`` section, and implement ``check``. ``base_dir`` is the
    pipeline file's directory, which relative paths are resolved from.
    """

    config_model: ClassVar[type[BaseModel]]

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        self.name = name
        self.config = config
        self.base_dir = base_dir

    def open(self) -> None:  # noqa: B027 - most connections acquire something
        """
        Acquire resources, such as clients or engines.
        """

    def close(self) -> None:  # noqa: B027
        """
        Release anything acquired in ``open``.
        """

    @abstractmethod
    def check(self) -> str:
        """
        Prove the connection works with one cheap real operation.

        Called after ``open``, to catch problems with credentials,
        permissions, network or drivers before a run. Raises if something
        is wrong; returns a short description of what was checked.
        """

    def not_open(self) -> ExecutionError:
        """
        The error to raise when the connection is used before ``open``.
        """
        return ExecutionError(f"Connection '{self.name}' is not open.")
