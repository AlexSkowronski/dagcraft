"""
The base class every file format extends.
"""

from abc import ABC, abstractmethod
from typing import Any, BinaryIO, ClassVar

from dagcraft.extras import require_extra


class Format(ABC):
    """
    Turns an open binary file into a table, and a table back into a file.

    ``extensions`` lists the file suffixes this format is inferred from.
    ``modules`` and ``extra`` name optional dependencies and the dagcraft
    extra that installs them. A format with ``multiple_inputs`` can write
    several tables to one file; ``write`` then receives a dict of them.
    """

    extensions: ClassVar[tuple[str, ...]] = ()
    modules: ClassVar[tuple[str, ...]] = ()
    extra: ClassVar[str] = ""
    multiple_inputs: ClassVar[bool] = False

    def check_available(self) -> None:
        """
        Raise ``ConfigError`` if an optional dependency is missing.
        """
        if self.modules:
            require_extra(
                *self.modules,
                extra=self.extra,
                feature=f"Reading and writing {self.extensions[0]} files",
            )

    @abstractmethod
    def read(self, file: BinaryIO, **args: Any) -> Any:
        """
        Read ``file`` into a table; ``args`` are the step's ``args``.
        """

    @abstractmethod
    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        """
        Write ``data`` to ``file``; ``args`` are the step's ``args``.
        """
