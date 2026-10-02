from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dagcraft.core.runtime import PipelineResult


class DagcraftError(Exception):
    """
    Base Dagcraft exception.
    """


class ConfigError(DagcraftError):
    """
    Raised when pipeline configuration is invalid.
    """


class GraphError(DagcraftError):
    """
    Raised when the DAG cannot be compiled.
    """


class RegistryError(DagcraftError):
    """
    Raised when a registered component cannot be found.
    """


class ExecutionError(DagcraftError):
    """
    Raised when pipeline execution fails.
    """


class PipelineError(DagcraftError):
    """
    Raised by ``Pipeline.run`` when a step fails.

    ``result`` holds the outcome of every step, and the failing step's
    exception is chained as ``__cause__``.
    """

    def __init__(self, message: str, result: PipelineResult) -> None:
        super().__init__(message)
        self.result = result
