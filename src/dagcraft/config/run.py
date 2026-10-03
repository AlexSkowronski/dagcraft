"""
How one run behaves: the options of ``Pipeline.run`` and the command line.
"""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dagcraft.config.validation import format_validation_error
from dagcraft.exceptions import ConfigError


class RunOptions(BaseModel):
    """
    Options for one run of a pipeline, checked the same way however given.

    ``fail_fast`` skips every remaining step after the first failure.
    ``run_id`` names the run in logs and the result; random when unset.
    ``keep_outputs`` keeps every step's output on the result; when false,
    each output is dropped once no remaining step needs it. ``max_workers``
    overrides the pipeline file's: how many independent steps run at once.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    fail_fast: bool = False
    run_id: str | None = Field(default=None, min_length=1)
    keep_outputs: bool = True
    max_workers: int | None = Field(default=None, ge=1)

    @classmethod
    def parse(cls, **values: Any) -> Self:
        """
        Validate ``values``; raise ``ConfigError`` naming every problem.
        """
        try:
            return cls(**values)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid run options: {format_validation_error(exc)}"
            ) from exc
