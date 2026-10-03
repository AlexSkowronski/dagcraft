"""The top level of a pipeline file."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineMeta(BaseModel):
    """The ``pipeline`` section.

    ``max_workers`` is how many independent steps may run at once.
    ``env_file`` is a ``.env`` file, relative to the pipeline file, whose
    variables are loaded before anything else so ``${env:NAME}`` references
    and Azure sign-in can use them. Variables already set in the environment
    keep their values.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    max_workers: int = Field(default=1, ge=1)
    env_file: str | None = Field(default=None, min_length=1)


class PipelineConfig(BaseModel):
    """The pipeline file as written.

    Connections and steps stay raw dicts here: each is validated against the
    model of its registered type when the pipeline is compiled, after
    ``${...}`` references are filled in.
    """

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineMeta
    params: dict[str, Any] = Field(default_factory=dict)
    connections: dict[str, dict[str, Any]] = Field(default_factory=dict)
    steps: list[dict[str, Any]]
