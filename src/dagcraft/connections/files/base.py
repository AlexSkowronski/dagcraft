"""
The base class for connections to storage that holds files.
"""

from abc import abstractmethod
from contextlib import AbstractContextManager
from typing import BinaryIO, Literal

from dagcraft.connections.base import Connection

FileMode = Literal["rb", "wb"]


class FileConnection(Connection):
    """
    Storage that holds files: a folder, a blob container, a SharePoint library.

    Subclasses open files and list the ones matching a pattern; paths are
    relative to wherever the connection points. Turning files into tables
    is up to the file reader and writer and the formats they use.
    """

    @abstractmethod
    def open_file(self, path: str, mode: FileMode) -> AbstractContextManager[BinaryIO]:
        """
        Open ``path`` for reading (``"rb"``) or writing (``"wb"``).
        """

    @abstractmethod
    def glob(self, pattern: str) -> list[str]:
        """
        The files matching ``pattern``, relative to the connection.
        """

    def relative_path(self, path: str) -> str:
        """
        ``path``, from a list another step made, as a path in this connection.

        Paths are relative to the connection already; subclasses also accept
        other forms, such as full URLs. Raises ``ExecutionError`` for one
        that isn't in this connection.
        """
        return path

    def check_pattern(self, pattern: str) -> None:
        """
        Raise ``ValueError`` if ``pattern`` can't be matched here.

        Called when the pipeline compiles, for paths with wildcards, so an
        unsupported pattern is reported before anything runs.
        """
