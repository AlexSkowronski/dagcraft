"""SQL databases through SQLAlchemy.

Requires the ``sql`` extra (``pip install 'dagcraft[sql]'``) plus a driver
for your database. SQLite works out of the box.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dagcraft.connections.base import Connection, read_variable, require_extra
from dagcraft.exceptions import ExecutionError
from dagcraft.registry import register_connection

if TYPE_CHECKING:
    import sqlalchemy as sa


class SQLReadOptions(BaseModel):
    """Fields of a read step that uses a SQL connection.

    Set ``query`` (with ``:name`` placeholders filled from ``params``) or
    ``table`` (``name`` or ``schema.name``). ``args`` go to ``pandas.read_sql``.
    """

    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, min_length=1)
    table: str | None = Field(default=None, min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_source(self) -> Self:
        if (self.query is None) == (self.table is None):
            raise ValueError("Set exactly one of 'query' or 'table'.")

        if self.params and self.query is None:
            raise ValueError("'params' can only be used with 'query'.")

        if self.table is not None:
            split_table(self.table)
        return self


class SQLWriteOptions(BaseModel):
    """Fields of a write step that uses a SQL connection.

    ``if_exists`` decides what happens when the table already exists:
    ``fail``, ``append``, ``delete_rows`` (empty it but keep its definition)
    or ``replace`` (drop and recreate it). ``args`` go to
    ``DataFrame.to_sql``. The whole write runs in one transaction.
    """

    model_config = ConfigDict(extra="forbid")

    table: str = Field(min_length=1)
    if_exists: Literal["fail", "append", "delete_rows", "replace"] = "fail"
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("table")
    @classmethod
    def check_table(cls, table: str) -> str:
        split_table(table)
        return table


class SQLConnection(Connection):
    """Base for connections to SQL databases through a SQLAlchemy engine.

    Subclasses implement ``create_engine``; reading and writing is handled
    here. ``extra`` names the package extra that provides the dependencies.
    """

    read_options = SQLReadOptions
    write_options = SQLWriteOptions
    extra: ClassVar[str] = "sql"

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        require_extra("sqlalchemy", extra=self.extra)
        super().__init__(name, config, base_dir)
        self._engine: sa.Engine | None = None

    def create_engine(self) -> sa.Engine:
        raise NotImplementedError

    def open(self) -> None:
        self._engine = self.create_engine()

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    @property
    def engine(self) -> sa.Engine:
        if self._engine is None:
            raise ExecutionError(f"Connection '{self.name}' is not open.")
        return self._engine

    def read(self, options: SQLReadOptions) -> pd.DataFrame:
        import sqlalchemy as sa  # noqa: PLC0415

        with self.engine.connect() as connection:
            if options.query is not None:
                return pd.read_sql(
                    sa.text(options.query),
                    connection,
                    params=options.params,
                    **options.args,
                )

            if options.table is not None:
                schema, table = split_table(options.table)
                return pd.read_sql_table(
                    table,
                    connection,
                    schema=schema,
                    **options.args,
                )

        raise ExecutionError("A SQL read needs a 'query' or a 'table'.")

    def write(self, data: pd.DataFrame, options: SQLWriteOptions) -> None:
        schema, table = split_table(options.table)
        args = {"index": False, **options.args}

        with self.engine.begin() as connection:
            data.to_sql(
                table,
                connection,
                schema=schema,
                if_exists=options.if_exists,
                **args,
            )


class SQLConfig(BaseModel):
    """Set exactly one of ``url`` or ``url_env``."""

    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, min_length=1)
    url_env: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def check_url(self) -> Self:
        if (self.url is None) == (self.url_env is None):
            raise ValueError(
                "Set exactly one of 'url' or 'url_env' (an environment "
                "variable holding the URL, for URLs that contain passwords)."
            )
        return self


@register_connection("sql")
class GenericSQLConnection(SQLConnection):
    """Any database SQLAlchemy supports, given a database URL.

    A relative SQLite path is relative to the pipeline file's directory.
    """

    config_model = SQLConfig
    config: SQLConfig

    def create_engine(self) -> sa.Engine:
        import sqlalchemy as sa  # noqa: PLC0415

        if self.config.url is not None:
            url = sa.make_url(self.config.url)
        else:
            url = sa.make_url(
                read_variable(self.config.url_env or "", self.name, "URL")
            )

        database = url.database

        if (
            url.get_backend_name() == "sqlite"
            and database
            and database != ":memory:"
            and not Path(database).is_absolute()
        ):
            url = url.set(database=str(self.base_dir / database))

        return sa.create_engine(url, pool_pre_ping=True)


def split_table(table: str) -> tuple[str | None, str]:
    """Split ``name`` or ``schema.name`` into its schema and name."""
    match table.split("."):
        case [name] if name:
            return None, name
        case [schema, name] if schema and name:
            return schema, name

    raise ValueError(f"Table '{table}' should be written as 'name' or 'schema.name'.")
