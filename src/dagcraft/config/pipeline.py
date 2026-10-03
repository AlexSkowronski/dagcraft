"""
The top level of a pipeline file.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PipelineMeta(BaseModel):
    """
    The ``pipeline`` section.

    ``max_workers`` is how many independent steps may run at once.
    ``env_file`` is a ``.env`` file, relative to the folder you run from, whose
    variables are loaded before anything else so ``${env:NAME}`` references
    and Azure sign-in can use them. Variables already set in the environment
    keep their values.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    max_workers: int = Field(default=1, ge=1)
    env_file: str | None = Field(default=None, min_length=1)


class PipelineConfig(BaseModel):
    """
    The pipeline file as written.

    ``include`` lists files of shared connections, relative to the folder
    you run from; connections defined here override shared ones of the same
    name. Connections and steps stay raw dicts here: each is validated
    against the model of its registered type when the pipeline is compiled,
    after ``${...}`` references are filled in.
    """

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineMeta
    include: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    connections: dict[str, dict[str, Any]] = Field(default_factory=dict)
    steps: list[dict[str, Any]]


class SharedConnections(BaseModel):
    """
    A file of connections that pipelines ``include``: only ``connections``.
    """

    model_config = ConfigDict(extra="forbid")

    connections: dict[str, dict[str, Any]]

    @model_validator(mode="before")
    @classmethod
    def check_only_connections(cls, data: Any) -> Any:
        """
        Say plainly that nothing but connections can be shared.
        """
        if isinstance(data, dict):
            others = sorted(set(data) - {"connections"})

            if others:
                raise ValueError(
                    "An included file can only hold 'connections'; it has "
                    f"{', '.join(others)}."
                )
        return data
