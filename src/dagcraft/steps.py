from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.config import StepConfig
from dagcraft.exceptions import ConfigError
from dagcraft.registry import OPERATIONS, register_step

if TYPE_CHECKING:
    from dagcraft.connections import Connection
    from dagcraft.runtime import ExecutionContext


class BaseStep(ABC):
    """Base class for step types.

    ``config_model`` validates the step's entry in the pipeline file.
    ``prepare`` runs when the pipeline is compiled, so that references to
    operations, connections and so on are checked before anything runs.
    """

    config_model: ClassVar[type[StepConfig]] = StepConfig

    def __init__(self, config: StepConfig) -> None:
        self.config = config

    def prepare(self, connections: dict[str, Connection]) -> None:  # noqa: B027
        """Resolve and check references. Raise ``ValueError`` if invalid."""

    @abstractmethod
    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        raise NotImplementedError


class FunctionStepConfig(StepConfig):
    """Config shared by steps that call a function with inputs and args."""

    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_names(self) -> Self:
        overlap = set(self.inputs) & set(self.args)

        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"Names used in both inputs and args: {names}")
        return self


class TransformConfig(FunctionStepConfig):
    operation: str = Field(min_length=1)


class PythonConfig(FunctionStepConfig):
    callable: str = Field(min_length=1)


class ReadConfig(StepConfig):
    """Fields beyond these are defined by the connection's type."""

    model_config = ConfigDict(extra="allow")

    connection: str = "local"

    @model_validator(mode="after")
    def check_no_inputs(self) -> Self:
        if self.inputs:
            raise ValueError("A read step cannot have inputs.")
        return self


class WriteConfig(StepConfig):
    """Fields beyond these are defined by the connection's type."""

    model_config = ConfigDict(extra="allow")

    connection: str = "local"

    @model_validator(mode="after")
    def check_one_input(self) -> Self:
        if len(self.inputs) != 1:
            raise ValueError("A write step needs exactly one input.")
        return self


@register_step("read")
class ReadStep(BaseStep):
    config_model = ReadConfig
    config: ReadConfig
    options: BaseModel

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)

        if connection.read_options is None:
            raise ValueError(
                f"Connection '{connection.name}' does not support reading."
            )

        self.options = connection.read_options.model_validate(
            self.config.model_extra or {}
        )

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        connection = context.connection(self.config.connection)

        return connection.read(self.options)


@register_step("write")
class WriteStep(BaseStep):
    config_model = WriteConfig
    config: WriteConfig
    options: BaseModel

    def prepare(self, connections: dict[str, Connection]) -> None:
        connection = find_connection(connections, self.config.connection)

        if connection.write_options is None:
            raise ValueError(
                f"Connection '{connection.name}' does not support writing."
            )

        self.options = connection.write_options.model_validate(
            self.config.model_extra or {}
        )

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        (data,) = inputs.values()

        connection = context.connection(self.config.connection)
        connection.write(data, self.options)

        return data


@register_step("transform")
class TransformStep(BaseStep):
    config_model = TransformConfig
    config: TransformConfig
    function: Callable[..., Any]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.function = OPERATIONS.get(self.config.operation)

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        return self.function(
            **inputs,
            **self.config.args,
        )


@register_step("python")
class PythonStep(BaseStep):
    config_model = PythonConfig
    config: PythonConfig
    function: Callable[..., Any]

    def prepare(self, connections: dict[str, Connection]) -> None:
        self.function = load_callable(self.config.callable)

    def execute(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> Any:
        return self.function(
            **inputs,
            **self.config.args,
        )


def find_connection(
    connections: dict[str, Connection],
    name: str,
) -> Connection:
    try:
        return connections[name]
    except KeyError:
        available = ", ".join(sorted(connections))
        raise ValueError(
            f"Unknown connection '{name}'. Available: {available}."
        ) from None


def load_callable(path: str) -> Callable[..., Any]:
    if ":" not in path:
        raise ConfigError(
            "Python callable must use the format 'module.path:function_name'."
        )

    module_name, function_name = path.split(
        ":",
        maxsplit=1,
    )

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
