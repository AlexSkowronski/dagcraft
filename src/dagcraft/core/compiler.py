"""Turn a pipeline file into connections, prepared steps and a graph."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# Importing operations registers the built-in operations.
from dagcraft import operations as _operations  # noqa: F401
from dagcraft.connections import Connection, LocalConfig, LocalConnection
from dagcraft.core.config import PipelineConfig, format_validation_error
from dagcraft.core.graph import CompiledGraph, compile_graph
from dagcraft.exceptions import ConfigError, DagcraftError
from dagcraft.registry import CONNECTIONS, STEPS
from dagcraft.steps import BaseStep


@dataclass(frozen=True)
class CompiledPipeline:
    name: str
    connections: dict[str, Connection]
    steps: dict[str, BaseStep]
    graph: CompiledGraph


def compile_pipeline(config: PipelineConfig, base_dir: Path) -> CompiledPipeline:
    connections = build_connections(config.connections, base_dir)
    steps = build_steps(config.steps)

    for step_id, step in steps.items():
        try:
            step.prepare(connections)
        except (ValueError, DagcraftError) as exc:
            raise ConfigError(f"Step '{step_id}': {describe(exc)}") from exc

    graph = compile_graph([step.config for step in steps.values()])

    return CompiledPipeline(
        name=config.pipeline.name,
        connections=connections,
        steps=steps,
        graph=graph,
    )


def build_connections(
    raw_connections: dict[str, dict[str, Any]],
    base_dir: Path,
) -> dict[str, Connection]:
    # A "local" connection rooted at the pipeline file's directory is always
    # available; defining one in the file replaces it.
    connections: dict[str, Connection] = {
        "local": LocalConnection("local", LocalConfig(), base_dir),
    }

    for name, raw in raw_connections.items():
        fields = dict(raw)
        connection_type = fields.pop("type", None)

        if not isinstance(connection_type, str):
            raise ConfigError(f"Connection '{name}' needs a 'type'.")

        try:
            connection_class = CONNECTIONS.get(connection_type)
            connection_config = connection_class.config_model.model_validate(fields)
            connections[name] = connection_class(name, connection_config, base_dir)
        except (ValueError, DagcraftError) as exc:
            raise ConfigError(f"Connection '{name}': {describe(exc)}") from exc

    return connections


def build_steps(raw_steps: list[dict[str, Any]]) -> dict[str, BaseStep]:
    steps: dict[str, BaseStep] = {}

    for position, raw in enumerate(raw_steps, start=1):
        step_id = raw.get("id")
        label = f"'{step_id}'" if isinstance(step_id, str) else f"#{position}"
        step_type = raw.get("type")

        if not isinstance(step_type, str):
            raise ConfigError(f"Step {label} needs a 'type'.")

        try:
            step_class = STEPS.get(step_type)
            step_config = step_class.config_model.model_validate(raw)
        except (ValueError, DagcraftError) as exc:
            raise ConfigError(f"Step {label}: {describe(exc)}") from exc

        if step_config.id in steps:
            raise ConfigError(f"Duplicate step id: '{step_config.id}'.")

        steps[step_config.id] = step_class(step_config)

    return steps


def describe(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return format_validation_error(exc)
    return str(exc)
