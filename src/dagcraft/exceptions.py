"""Errors raised by dagcraft. Catch ``PipelineError`` to handle any of them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only for annotations: everything imports this module, so it imports
    # nothing of dagcraft's at run time, which rules out import cycles.
    from dagcraft.core.results import PipelineResult


class PipelineError(Exception):
    """Base class for every error dagcraft raises."""


class ConfigError(PipelineError):
    """The pipeline file is invalid: raised before anything runs."""


class GraphError(ConfigError):
    """The steps don't form a valid graph, such as a cycle or an unknown input."""


class RegistryError(PipelineError):
    """A step type, format or other component is unknown or registered twice."""


class ExecutionError(PipelineError):
    """A step or connection couldn't do its work while the pipeline ran."""


class RunError(PipelineError):
    """Raised by ``Pipeline.run`` when a step fails.

    ``result`` holds the outcome of every step, and the first failing step's
    exception is chained as ``__cause__``.
    """

    def __init__(self, message: str, result: PipelineResult) -> None:
        super().__init__(message)
        self.result = result

    @classmethod
    def from_result(cls, result: PipelineResult) -> RunError:
        """Build the error for a run with failed steps, naming each of them."""
        first, *others = result.failed_steps
        message = f"Pipeline '{result.name}' failed at step '{first.id}': {first.error}"

        if others:
            message += f" (also failed: {', '.join(step.id for step in others)})"

        return cls(message, result)
