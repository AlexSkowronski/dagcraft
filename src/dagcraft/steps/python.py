"""
The ``python`` step: call your own function with its inputs.
"""

from collections.abc import Callable
from typing import Any

from dagcraft.config.steps import PythonConfig
from dagcraft.connections import Connection
from dagcraft.core.context import ExecutionContext
from dagcraft.imports import load_callable
from dagcraft.registry import register_step
from dagcraft.steps.base import BaseStep


@register_step("python")
class PythonStep(BaseStep):
    """
    Calls ``callable`` with the inputs, by name, plus ``args``.
    """

    config_model = PythonConfig
    config: PythonConfig
    function: Callable[..., Any]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.function = load_callable(self.config.callable)

    def describe(self) -> str:
        return f"call {self.config.callable}"

    def execute(self, context: ExecutionContext, inputs: dict[str, Any]) -> Any:
        return self.function(**inputs, **self.config.args)
