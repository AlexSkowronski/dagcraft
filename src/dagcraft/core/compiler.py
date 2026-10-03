"""
Turning a pipeline file into connections, prepared steps and a graph.

Everything that can be checked without running is checked here, so a
pipeline that compiles is one that can run.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# Importing these packages registers the built-in components.
from dagcraft import operations as _operations  # noqa: F401
from dagcraft import readers as _readers  # noqa: F401
from dagcraft import writers as _writers  # noqa: F401
from dagcraft.config import PipelineConfig, format_validation_error
from dagcraft.config.connections import LocalConfig
from dagcraft.connections import Connection, LocalConnection
from dagcraft.core.graph import CompiledGraph, compile_graph
from dagcraft.core.params import resolve_params, substitute
from dagcraft.env import load_env_file
from dagcraft.exceptions import ConfigError, PipelineError
from dagcraft.registry import CONNECTIONS, STEPS
from dagcraft.steps import BaseStep


@dataclass(frozen=True)
class CompiledPipeline:
    """
    A checked pipeline: its connections and prepared steps, in graph order.
    """

    name: str
    params: dict[str, Any]
    connections: dict[str, Connection]
    connection_types: dict[str, str]
    steps: dict[str, BaseStep]
    graph: CompiledGraph


def compile_pipeline(
    config: PipelineConfig,
    base_dir: Path,
    params: dict[str, Any] | None = None,
) -> CompiledPipeline:
    """
    Check ``config`` and build everything needed to run it.

    Raises ``ConfigError`` naming the connection or step at fault.
    """
    if config.pipeline.env_file is not None:
        load_env_file(base_dir / config.pipeline.env_file)

    values = resolve_params(config.params, params or {})
    connections, connection_types = build_connections(
        config.connections, base_dir, values
    )
    steps = build_steps(config.steps, values)

    for step_id, step in steps.items():
        try:
            step.prepare(connections)
        except (ValueError, PipelineError) as exc:
            raise ConfigError(f"Step '{step_id}': {describe(exc)}") from exc

    graph = compile_graph(
        {step_id: set(step.config.inputs.values()) for step_id, step in steps.items()}
    )

    return CompiledPipeline(
        name=config.pipeline.name,
        params=values,
        connections=connections,
        connection_types=connection_types,
        steps=steps,
        graph=graph,
    )


def build_connections(
    raw_connections: dict[str, dict[str, Any]],
    base_dir: Path,
    params: dict[str, Any],
) -> tuple[dict[str, Connection], dict[str, str]]:
    """
    Create each connection from its section, plus the built-in ``local``.

    Returns the connections and each one's type name, by connection name.
    """
    # A "local" connection rooted at the pipeline file's directory is always
    # available; defining one in the file replaces it.
    connections: dict[str, Connection] = {
        "local": LocalConnection("local", LocalConfig(), base_dir),
    }
    types = {"local": "local"}

    for name, raw in raw_connections.items():
        try:
            fields = substitute(raw, params)
        except ValueError as exc:
            raise ConfigError(f"Connection '{name}': {exc}") from exc

        connection_type = fields.pop("type", None)

        if not isinstance(connection_type, str):
            raise ConfigError(f"Connection '{name}' needs a 'type'.")

        try:
            connection_class = CONNECTIONS.get(connection_type)
            connection_config = connection_class.config_model.model_validate(fields)
            connections[name] = connection_class(name, connection_config, base_dir)
        except (ValueError, PipelineError) as exc:
            raise ConfigError(f"Connection '{name}': {describe(exc)}") from exc

        types[name] = connection_type

    return connections, types


def build_steps(
    raw_steps: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, BaseStep]:
    """
    Create each step from its entry, validated by its type's model.
    """
    steps: dict[str, BaseStep] = {}

    for position, raw in enumerate(raw_steps, start=1):
        step_id = raw.get("id")
        label = f"'{step_id}'" if isinstance(step_id, str) else f"#{position}"

        try:
            fields = substitute(raw, params)
        except ValueError as exc:
            raise ConfigError(f"Step {label}: {exc}") from exc

        step_type = fields.get("type")

        if not isinstance(step_type, str):
            raise ConfigError(f"Step {label} needs a 'type'.")

        try:
            step_class = STEPS.get(step_type)
            step_config = step_class.config_model.model_validate(fields)
        except (ValueError, PipelineError) as exc:
            raise ConfigError(f"Step {label}: {describe(exc)}") from exc

        if step_config.id in steps:
            raise ConfigError(f"Duplicate step id: '{step_config.id}'.")

        steps[step_config.id] = step_class(step_config)

    return steps


def describe(exc: Exception) -> str:
    """
    An error's message, with validation errors summarised on one line.
    """
    if isinstance(exc, ValidationError):
        return format_validation_error(exc)
    return str(exc)
