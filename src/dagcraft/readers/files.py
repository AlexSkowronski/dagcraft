"""
Reading files: one path, or every file matching a pattern.
"""

import pandas as pd

from dagcraft.config.readers import FileReadOptions
from dagcraft.connections.files import FileConnection
from dagcraft.exceptions import ExecutionError
from dagcraft.formats import Format, resolve_format
from dagcraft.logs import get_logger
from dagcraft.paths import has_wildcards
from dagcraft.readers.base import Reader
from dagcraft.registry import register_reader

logger = get_logger(__name__)


@register_reader(FileConnection)
class FileReader(Reader):
    """
    Reads ``path`` from any file connection with its format.

    A path with wildcards reads every matching file, in name order, into
    one table.
    """

    options_model = FileReadOptions
    options: FileReadOptions

    @property
    def file_format(self) -> Format:
        """
        The format named in the options, or implied by the path.
        """
        return resolve_format(self.options.path, self.options.format)

    def prepare(self, connection: FileConnection) -> None:
        self.file_format.check_available()

        if has_wildcards(self.options.path):
            connection.check_pattern(self.options.path)

    def describe(self) -> str:
        return self.options.path

    def read(self, connection: FileConnection) -> pd.DataFrame:
        pattern = self.options.path

        if not has_wildcards(pattern):
            return self._read_file(connection, pattern)

        paths = sorted(connection.glob(pattern))

        if not paths:
            raise ExecutionError(
                f"No files in connection '{connection.name}' match '{pattern}'."
            )

        logger.info("found %d files matching %s", len(paths), pattern)
        frames = []

        for path in paths:
            frame = self._read_file(connection, path)

            if self.options.source_column is not None:
                frame[self.options.source_column] = path

            frames.append(frame)

        return pd.concat(frames, ignore_index=True)

    def _read_file(self, connection: FileConnection, path: str) -> pd.DataFrame:
        logger.debug("reading %s", path)

        with connection.open_file(path, "rb") as file:
            return self.file_format.read(file, **self.options.args)
