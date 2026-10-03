"""
Reading files: one path, every file matching a pattern, or files another step lists.
"""

from pathlib import PurePath
from typing import Any

import pandas as pd

from dagcraft.config.readers import FileReadOptions
from dagcraft.connections.files import FileConnection
from dagcraft.data import count
from dagcraft.exceptions import ExecutionError
from dagcraft.formats import Format, resolve_format
from dagcraft.logs import get_logger
from dagcraft.paths import has_wildcards
from dagcraft.readers.base import Reader
from dagcraft.readers.listed_paths import listed_paths
from dagcraft.registry import register_reader
from dagcraft.threads import map_in_threads

logger = get_logger(__name__)


@register_reader(FileConnection)
class FileReader(Reader):
    """
    Reads files from any file connection with their format.

    One ``path``; every file matching a ``path`` with wildcards, in name
    order; or the files another step lists, as a ``paths`` input. Several
    files are read up to ``parallel`` at once, and the format combines them:
    tables into one table, documents into a list.
    """

    options_model = FileReadOptions
    options: FileReadOptions
    accepts_paths = True

    def prepare(self, connection: FileConnection) -> None:
        path = self.options.path

        # Listed files' format is only known now if it's named.
        if path is not None or self.options.format is not None:
            file_format = resolve_format(path or "", self.options.format)
            file_format.check_available()
            file_format.check_args(self.options.args)

        if path is not None and has_wildcards(path):
            connection.check_pattern(path)

    def expect_paths(self, listed: bool) -> None:
        if listed and self.options.path is not None:
            raise ValueError("Set 'path' or give a 'paths' input, not both.")
        if not listed and self.options.path is None:
            raise ValueError(
                "Set 'path', or give a 'paths' input listing the files to read."
            )
        if not listed and self.options.path_column is not None:
            raise ValueError("'path_column' only applies with a 'paths' input.")

    def describe(self) -> str:
        return self.options.path or ""

    def read(self, connection: FileConnection) -> Any:
        pattern = self.options.path or ""

        if not has_wildcards(pattern):
            return self._read_file(connection, pattern, self._format_of([pattern]))

        paths = sorted(connection.glob(pattern))
        logger.info("found %s matching %s", count(len(paths), "file"), pattern)
        return self._read_files(connection, paths, self._format_of(paths, pattern))

    def read_listed(self, connection: FileConnection, listed: Any) -> Any:
        paths = [
            connection.relative_path(path)
            for path in listed_paths(listed, self.options.path_column)
        ]
        logger.info("reading %s listed by another step", count(len(paths), "file"))

        if not paths and self.options.format is None:
            return pd.DataFrame()  # nothing to read, and no format to say more

        file_format = self._format_of(paths)
        file_format.check_available()
        return self._read_files(connection, paths, file_format)

    def _read_files(
        self,
        connection: FileConnection,
        paths: list[str],
        file_format: Format,
    ) -> Any:
        def read_one(path: str) -> tuple[str, Any]:
            return path, self._read_file(connection, path, file_format)

        parts = map_in_threads(
            read_one,
            paths,
            workers=self.options.parallel,
            name="dagcraft-files",
        )
        return file_format.combine(parts, self.options.source_column)

    def _format_of(self, paths: list[str], pattern: str = "") -> Format:
        """
        The format to read ``paths`` with: the one named, or their extension's.

        With no paths, a pattern such as ``*.json`` still says. Raises
        ``ExecutionError`` if the paths' extensions disagree.
        """
        if self.options.format is not None:
            return resolve_format("", self.options.format)

        suffixes = sorted(
            {PurePath(path).suffix.lower() for path in paths or [pattern]}
        )

        if len(suffixes) > 1:
            raise ExecutionError(
                f"The files are in different formats ({', '.join(suffixes)}): set "
                "'format' to read them all one way."
            )

        try:
            return resolve_format((paths or [pattern])[0])
        except ValueError as exc:
            raise ExecutionError(str(exc)) from None

    def _read_file(
        self,
        connection: FileConnection,
        path: str,
        file_format: Format,
    ) -> Any:
        logger.debug("reading %s", path)

        with connection.open_file(path, "rb") as file:
            return file_format.read(file, **self.options.args)
