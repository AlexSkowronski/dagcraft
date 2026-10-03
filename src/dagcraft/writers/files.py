"""Writing a file in the format its path or the step names."""

from typing import Any

from dagcraft.config.writers import FileWriteOptions
from dagcraft.connections.files import FileConnection
from dagcraft.formats import Format, resolve_format
from dagcraft.registry import register_writer
from dagcraft.writers.base import Writer


@register_writer(FileConnection)
class FileWriter(Writer):
    """Writes ``path`` to any file connection with its format."""

    options_model = FileWriteOptions
    options: FileWriteOptions

    @property
    def file_format(self) -> Format:
        """The format named in the options, or implied by the path."""
        return resolve_format(self.options.path, self.options.format)

    def prepare(self, connection: FileConnection) -> None:
        self.file_format.check_available()

    def describe(self) -> str:
        return self.options.path

    def accepts_multiple_inputs(self) -> bool:
        return self.file_format.multiple_inputs

    def write(self, connection: FileConnection, data: Any) -> None:
        with connection.open_file(self.options.path, "wb") as file:
            self.file_format.write(data, file, **self.options.args)
