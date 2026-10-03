"""
The base class every step type extends.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from dagcraft.config.steps import StepConfig
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext


class BaseStep(ABC):
    """
    One node of the pipeline graph.

    ``config_model`` validates the step's entry in the pipeline file.
    ``prepare`` runs when the pipeline compiles, so references to
    operations, connections and so on are checked before anything runs.
    ``execute`` receives the outputs of the steps named in ``inputs``, by
    input name, and returns this step's output.
    """

    config_model: ClassVar[type[StepConfig]] = StepConfig

    def __init__(self, config: StepConfig) -> None:
        self.config = config

    def prepare(self, connections: dict[str, Connection]) -> None:  # noqa: B027
        """
        Resolve and check references. Raise ``ValueError`` if invalid.
        """

    def describe(self) -> str:
        """
        A one-line description of what the step does, for dry runs and logs.
        """
        return self.config.type

    def connection_name(self) -> str | None:
        """
        The connection this step uses, if any.
        """
        return None

    @abstractmethod
    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        """
        Do the step's work and return its output.
        """
