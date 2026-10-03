"""The fields of a write step, for each kind of connection."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.paths import WILDCARDS, has_wildcards


class FileWriteOptions(BaseModel):
    """Writing to a file connection.

    ``format`` is inferred from the file extension unless set; ``args`` go
    to the format's writer (``DataFrame.to_csv`` and so on).
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    format: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_path(self) -> Self:
        """A write goes to one file, so the path can't be a pattern."""
        if has_wildcards(self.path):
            raise ValueError(f"A path to write can't contain wildcards ({WILDCARDS}).")
        return self


class SQLWriteOptions(BaseModel):
    """Writing to a SQL connection.

    ``table`` is ``name`` or ``schema.name``. ``if_exists`` decides what
    happens when the table already exists: ``fail``, ``append``,
    ``delete_rows`` (empty it but keep its definition) or ``replace`` (drop
    and recreate it). ``args`` go to ``DataFrame.to_sql``. The whole write
    runs in one transaction.
    """

    model_config = ConfigDict(extra="forbid")

    table: str = Field(min_length=1)
    if_exists: Literal["fail", "append", "delete_rows", "replace"] = "fail"
    args: dict[str, Any] = Field(default_factory=dict)
