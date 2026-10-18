"""
The top level of a pipeline file.
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MODULE_NAME = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*")


class PipelineMeta(BaseModel):
    """
    The ``pipeline`` section.

    ``max_workers`` is how many independent steps may run at once.
    ``env_file`` is a ``.env`` file, relative to the folder you run from, whose
    variables are loaded before anything else so ``${env:NAME}`` references
    and Azure sign-in can use them. Variables already set in the environment
    keep their values. ``imports`` lists modules of yours to import next, so
    the operations, step types, connections and formats they register can be
    named in the file, with the ``dagcraft`` command as well as from Python.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    max_workers: int = Field(default=1, ge=1)
    env_file: str | None = Field(default=None, min_length=1)
    imports: list[str] = Field(default_factory=list)

    @field_validator("imports")
    @classmethod
    def check_imports(cls, names: list[str]) -> list[str]:
        """
        Modules are written as Python imports them, not as files.
        """
        for name in names:
            if not MODULE_NAME.fullmatch(name):
                raise ValueError(
                    f"'{name}' isn't a module name: write it as you would "
                    "import it, such as my_project.cleaning."
                )
        return names


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
