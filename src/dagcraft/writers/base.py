"""
The base class for writers: where a write step puts its data.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from dagcraft.templates import Templates


class Writer(ABC):
    """
    Writes data to one kind of connection, as a write step's fields say.

    Register a writer for a connection type with ``register_writer``.
    ``options_model`` validates the step's own fields (``path``, ``table``
    and so on); its ``template_fields`` are Jinja templates, rendered before
    they're checked. ``prepare`` runs when the pipeline compiles; ``write``
    runs during the run, with the connection open.
    """

    options_model: ClassVar[type[BaseModel]]
    template_fields: ClassVar[tuple[str, ...]] = ()

    def __init__(self, options: Any) -> None:
        self.options = options

    def prepare(  # noqa: B027 - optional hook
        self,
        connection: Any,
        templates: Templates,
    ) -> None:
        """
        Check the options against the connection. Raise ``ValueError``.

        ``templates`` renders any other text the options name.
        """

    def describe(self) -> str:
        """
        Where data is written, for dry runs and logs.
        """
        return ""

    def accepts_multiple_inputs(self) -> bool:
        """
        Whether ``write`` can take several inputs at once, as a dict.
        """
        return False

    @abstractmethod
    def write(self, connection: Any, data: Any) -> None:
        """
        Write ``data`` to the open ``connection``.
        """
