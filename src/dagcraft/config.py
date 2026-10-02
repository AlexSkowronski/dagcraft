from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PipelineMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class StepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: str = Field(min_length=1)

    connector: str | None = None
    operation: str | None = None
    callable: str | None = None

    inputs: dict[str, str] = Field(default_factory=dict)
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_step(self) -> Self:
        overlapping_names = set(self.inputs) & set(self.args)

        if overlapping_names:
            names = ", ".join(sorted(overlapping_names))
            raise ValueError(
                f"Step '{self.id}' contains names in both "
                f"inputs and args: {names}"
            )
        if self.type == "read":
            if not self.connector:
                raise ValueError(
                    f"Read step '{self.id}' requires a connector."
                )
            if self.inputs:
                raise ValueError(
                    f"Read step '{self.id}' cannot have upstream inputs."
                )
        elif self.type == "transform":
            if not self.operation:
                raise ValueError(
                    f"Transform step '{self.id}' requires an operation."
                )
        elif self.type == "python":
            if not self.callable:
                raise ValueError(
                    f"Python step '{self.id}' requires a callable."
                )
        elif self.type == "write":
            if not self.connector:
                raise ValueError(
                    f"Write step '{self.id}' requires a connector."
                )
            if not self.inputs:
                raise ValueError(
                    f"Write step '{self.id}' requires at least one input."
                )
        return self


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineMeta
    steps: list[StepConfig]

    @model_validator(mode="after")
    def validate_unique_step_ids(self) -> Self:
        ids = [step.id for step in self.steps]

        duplicates = {
            step_id
            for step_id in ids
            if ids.count(step_id) > 1
        }

        if duplicates:
            duplicate_names = ", ".join(sorted(duplicates))

            raise ValueError(
                f"Duplicate step ids found: {duplicate_names}"
            )
        return self
    