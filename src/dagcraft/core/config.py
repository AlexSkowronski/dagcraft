from __future__ import annotations

import re
from typing import IO, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

BOOL_TAG = "tag:yaml.org,2002:bool"


class PipelineLoader(yaml.SafeLoader):
    """SafeLoader where only true/false are booleans, as in YAML 1.2.

    PyYAML follows YAML 1.1, which also reads yes, no, on and off as
    booleans, so ``on: customer_id`` would become ``{True: "customer_id"}``.
    """


PipelineLoader.yaml_implicit_resolvers = {
    first: [(tag, pattern) for tag, pattern in resolvers if tag != BOOL_TAG]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
PipelineLoader.add_implicit_resolver(
    BOOL_TAG,
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_yaml(stream: IO[str]) -> Any:
    return yaml.load(stream, Loader=PipelineLoader)  # noqa: S506 - a SafeLoader


class PipelineMeta(BaseModel):
    """``max_workers`` is how many independent steps may run at once."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    max_workers: int = Field(default=1, ge=1)


class PipelineConfig(BaseModel):
    """The pipeline file as written.

    Each step and connection is validated against its registered type when
    the pipeline is compiled.
    """

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineMeta
    params: dict[str, Any] = Field(default_factory=dict)
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
