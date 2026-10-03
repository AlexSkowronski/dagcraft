"""
Connections shared between pipelines, from the files they ``include``.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dagcraft.config.pipeline import SharedConnections
from dagcraft.config.validation import format_validation_error
from dagcraft.exceptions import ConfigError
from dagcraft.yaml_loader import load_yaml


@dataclass(frozen=True)
class SharedConnection:
    """
    A connection's section as an included file writes it, and that file.
    """

    file: str
    fields: dict[str, Any]


def load_shared_connections(
    files: list[str],
    base_dir: Path,
) -> dict[str, SharedConnection]:
    """
    Every connection the included ``files`` define, by name.

    Raises ``ConfigError`` for a missing or invalid file, or a name two
    files both define.
    """
    shared: dict[str, SharedConnection] = {}

    for file in files:
        for name, fields in read_shared_file(base_dir / file, file).items():
            if name in shared:
                raise ConfigError(
                    f"Connection '{name}' is defined in both {shared[name].file} "
                    f"and {file}."
                )
            shared[name] = SharedConnection(file, fields)

    return shared


def read_shared_file(path: Path, file: str) -> dict[str, dict[str, Any]]:
    """
    The connections in one included file; ``file`` is how errors name it.
    """
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
    except OSError:
        raise ConfigError(
            f"Included file not found: {file} (looked for {path})."
        ) from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in included file {file}: {exc}") from exc

    try:
        return SharedConnections.model_validate(raw).connections
    except ValidationError as exc:
        raise ConfigError(f"{file}: {format_validation_error(exc)}") from exc
