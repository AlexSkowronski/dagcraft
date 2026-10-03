"""The ``python`` step: call your own function with its inputs."""

import importlib
from collections.abc import Callable
from typing import Any

from dagcraft.config.steps import PythonConfig
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.exceptions import ConfigError
from dagcraft.registry import register_step
from dagcraft.steps.base import BaseStep


@register_step("python")
class PythonStep(BaseStep):
    """Calls ``callable`` with the inputs, by name, plus ``args``."""

    config_model = PythonConfig
    config: PythonConfig
    function: Callable[..., Any]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.function = load_callable(self.config.callable)

    def describe(self) -> str:
        return f"call {self.config.callable}"

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        return self.function(**inputs, **self.config.args)


def load_callable(path: str) -> Callable[..., Any]:
    """Import ``module.path:function`` and return the function."""
    if ":" not in path:
        raise ConfigError(
            "Python callable must use the format 'module.path:function_name'."
        )

    module_name, function_name = path.split(":", maxsplit=1)

    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"Could not import module '{module_name}'.") from exc

    function = getattr(module, function_name, None)

    if function is None:
        raise ConfigError(
            f"Module '{module_name}' has no callable named '{function_name}'."
        )

    if not callable(function):
        raise ConfigError(f"'{path}' is not callable.")

    return function
