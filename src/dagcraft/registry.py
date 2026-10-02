from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dagcraft.exceptions import RegistryError


STEP_REGISTRY: dict[str, type[Any]] = {}
CONNECTOR_REGISTRY: dict[str, Any] = {}
OPERATION_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_step(name: str):
    def decorator(step_class):
        STEP_REGISTRY[name] = step_class
        return step_class

    return decorator


def register_connector(name: str):
    def decorator(connector_class):
        CONNECTOR_REGISTRY[name] = connector_class()
        return connector_class

    return decorator


def register_operation(name: str):
    def decorator(operation):
        OPERATION_REGISTRY[name] = operation
        return operation

    return decorator


def get_step(name: str):
    try:
        return STEP_REGISTRY[name]
    except KeyError as exc:
        raise RegistryError(
            f"Unknown step type: '{name}'"
        ) from exc


def get_connector(name: str):
    try:
        return CONNECTOR_REGISTRY[name]
    except KeyError as exc:
        raise RegistryError(
            f"Unknown connector: '{name}'"
        ) from exc


def get_operation(name: str):
    try:
        return OPERATION_REGISTRY[name]
    except KeyError as exc:
        raise RegistryError(
            f"Unknown operation: '{name}'"
        ) from exc