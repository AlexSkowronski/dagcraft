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


class TransformConfig(StepConfig):
    """
    A ``transform`` step: ``operations`` applied in order to its ``data`` input.

    Each operation is written ``name: {option: value}``, ``name: value`` for
    its main option, or just ``name``. Other inputs can be named in options
    that take a table, such as a join's ``right``.
    """

    operations: list[str | dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def check_old_form(cls, data: Any) -> Any:
        """
        Point ``operation`` and ``args``, the form before 0.1.0, to ``operations``.
        """
        if isinstance(data, dict) and "operation" in data:
            raise ValueError(
                "A transform lists its operations: write "
                "'operations: [{filter: amount > 100}]' instead of "
                "'operation:' and 'args:'."
            )
        return data

    @model_validator(mode="after")
    def check_operations(self) -> Self:
        """
        The chain starts from ``data``, and each entry is one operation.
        """
        if "data" not in self.inputs:
            raise ValueError(
                "A transform needs a 'data' input: the table its operations start from."
            )

        for position, entry in enumerate(self.operations, start=1):
            if isinstance(entry, dict) and len(entry) != 1:
                raise ValueError(
                    f"Operation {position} should be one operation, such as "
                    "'filter: amount > 100'."
                )
        return self


class PythonConfig(StepConfig):
    """
    A ``python`` step: calls ``callable``, written as ``module.path:function``.

    The step's inputs, by name, and ``args`` are passed as keyword arguments.
    """

    callable: str = Field(min_length=1)
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
