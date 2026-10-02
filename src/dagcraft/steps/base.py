from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from dagcraft.connections import Connection
    from dagcraft.core.runtime import ExecutionContext


class StepConfig(BaseModel):
    """Fields every step has. Step types subclass this to add their own."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    inputs: dict[str, str] = Field(default_factory=dict)


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
