from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from typing import Any

# Import these modules so built-ins register themselves.
from dagcraft import connectors as _connectors  # noqa: F401
from dagcraft import operations as _operations  # noqa: F401
from dagcraft.config import StepConfig
from dagcraft.exceptions import ExecutionError
from dagcraft.registry import (
    get_connector,
    get_operation,
    register_step,
)
from dagcraft.runtime import ExecutionContext


class BaseStep(ABC):
    def __init__(self, config: StepConfig):
        self.config = config

    @abstractmethod
    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        raise NotImplementedError


@register_step("read")
class ReadStep(BaseStep):
    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        assert self.config.connector is not None

        connector = get_connector(self.config.connector)

        return connector.read(**self.config.args)


@register_step("transform")
class TransformStep(BaseStep):
    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        assert self.config.operation is not None

        operation = get_operation(self.config.operation)

        return operation(
            **inputs,
            **self.config.args,
        )


@register_step("python")
class PythonStep(BaseStep):
    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        assert self.config.callable is not None

        function = load_callable(self.config.callable)

        return function(
            **inputs,
            **self.config.args,
        )


@register_step("write")
class WriteStep(BaseStep):
    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        assert self.config.connector is not None

        connector = get_connector(self.config.connector)

        return connector.write(
            **inputs,
            **self.config.args,
        )


def load_callable(path: str):
    if ":" not in path:
        raise ExecutionError(
            "Python callable must use the format 'module.path:function_name'."
        )

    module_name, function_name = path.split(
        ":",
        maxsplit=1,
    )

    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ExecutionError(f"Could not import module '{module_name}'.") from exc

    try:
        function = getattr(
            module,
            function_name,
        )
    except AttributeError as exc:
        raise ExecutionError(
            f"Module '{module_name}' has no callable named '{function_name}'."
        ) from exc

    if not callable(function):
        raise ExecutionError(f"'{path}' is not callable.")

    return function
