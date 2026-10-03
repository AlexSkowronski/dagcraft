"""
The base class every file format extends.
"""

from abc import ABC, abstractmethod
from typing import Any, BinaryIO, ClassVar

import pandas as pd

from dagcraft.extras import require_extra


class Format(ABC):
    """
    Turns an open binary file into data, and data back into a file.

    Table formats (CSV, Parquet, Excel) read DataFrames; document formats
    (JSON, JSON Lines, YAML) read plain Python data. ``extensions`` lists the
    file suffixes this format is inferred from. ``modules`` and ``extra``
    name optional dependencies and the dagcraft extra that installs them. A
    format with ``multiple_inputs`` can write several tables to one file;
    ``write`` then receives a dict of them.
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

    def check_args(self, args: dict[str, Any]) -> None:  # noqa: B027 - optional
        """
        Raise ``ValueError`` for read ``args`` this format can't use.

        Called when the pipeline loads, so mistakes show up before a run.
        """

    @abstractmethod
    def read(self, file: BinaryIO, **args: Any) -> Any:
        """
        Read ``file``; ``args`` are the step's ``args``.
        """

    @abstractmethod
    def write(self, data: Any, file: BinaryIO, **args: Any) -> None:
        """
        Write ``data`` to ``file``; ``args`` are the step's ``args``.
        """

    def combine(self, parts: list[tuple[str, Any]], source_column: str | None) -> Any:
        """
        Combine what several files read, as ``(path, data)`` pairs, into one.

        Tables are stacked into one table; ``source_column`` adds a column
        naming each row's file.
        """
        frames = []

        for path, frame in parts:
            if source_column is not None:
                frame[source_column] = path
            frames.append(frame)

        return pd.concat(frames, ignore_index=True)
