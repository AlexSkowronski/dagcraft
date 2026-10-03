"""
The fields of each built-in step type.
"""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StepConfig(BaseModel):
    """
    Fields every step has. Step types subclass this to add their own.

    ``inputs`` maps the names a step receives its inputs under to the ids of
    the steps that produce them. ``retries`` re-runs a failed step that many
    more times, waiting ``retry_delay`` seconds before the first retry and
    twice as long before each one after that.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    inputs: dict[str, str] = Field(default_factory=dict)
    retries: int = Field(default=0, ge=0)
    retry_delay: float = Field(default=5.0, ge=0)


class FunctionStepConfig(StepConfig):
    """
    Steps that call a function with their inputs plus ``args``.
    """

    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_names(self) -> Self:
        """
        An argument can't share a name with an input.
        """
        overlap = set(self.inputs) & set(self.args)

        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"Names used in both inputs and args: {names}")
        return self


class TransformConfig(FunctionStepConfig):
    """
    A ``transform`` step: calls a registered operation.
    """

    operation: str = Field(min_length=1)


class PythonConfig(FunctionStepConfig):
    """
    A ``python`` step: calls ``callable``, written as ``module.path:function``.
    """

    callable: str = Field(min_length=1)


class ReadConfig(StepConfig):
    """
    A ``read`` step.

    The other fields (``path``, ``query``, ...) depend on the kind of
    connection, and are validated by its reader's options model.
    """

    model_config = ConfigDict(extra="allow")

    connection: str = "local"

    @model_validator(mode="after")
    def check_no_inputs(self) -> Self:
        """
        Reading starts a branch of the graph, so it takes no inputs.
        """
        if self.inputs:
            raise ValueError("A read step cannot have inputs.")
        return self


class WriteConfig(StepConfig):
    """
    A ``write`` step.

    The other fields depend on the kind of connection, and are validated by
    its writer's options model. Usually one input; formats that hold several
    tables, such as Excel, accept more.
    """

    model_config = ConfigDict(extra="allow")

    connection: str = "local"

    @model_validator(mode="after")
    def check_inputs(self) -> Self:
        """
        Writing needs something to write.
        """
        if not self.inputs:
            raise ValueError("A write step needs at least one input.")
        return self


def extra_fields(config: BaseModel) -> dict[str, Any]:
    """
    The fields a step was given beyond the ones its model defines.
    """
    return dict(config.model_extra or {})
