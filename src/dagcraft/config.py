from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class PipelineMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class StepConfig(BaseModel):
    """Fields every step has. Step types subclass this to add their own."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    inputs: dict[str, str] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """The pipeline file as written.

    Each step and connection is validated against its registered type when
    the pipeline is compiled.
    """

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineMeta
    connections: dict[str, dict[str, Any]] = Field(default_factory=dict)
    steps: list[dict[str, Any]]


def format_validation_error(exc: ValidationError) -> str:
    """Summarise a pydantic error as one line, one clause per problem."""
    problems = []

    for error in exc.errors():
        message = error["msg"].removeprefix("Value error, ")
        location = ".".join(str(part) for part in error["loc"])
        problems.append(f"{location}: {message}" if location else message)

    return "; ".join(problems)
