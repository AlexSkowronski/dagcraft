"""SQL databases through SQLAlchemy.

Requires the ``sql`` extra (``pip install 'dagcraft-pipelines[sql]'``) plus a driver
for your database. SQLite works out of the box.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dagcraft.connections.base import Connection, read_variable
from dagcraft.exceptions import ExecutionError
from dagcraft.extras import require_extra
from dagcraft.registry import register_connection

if TYPE_CHECKING:
    import sqlalchemy as sa


PARTITION_PLACEHOLDERS = ("partition_start", "partition_end")

# Extra pooled connections allowed beyond the usual 5, for partitioned reads
# and parallel steps.
POOL_OVERFLOW = 40


class SQLPartition(BaseModel):
    """Split a read into ranges of a whole-number column, read at the same time.

    Reading a ``table``, set ``column``: its range comes from the column's
    MIN and MAX unless ``lower`` and ``upper`` are set, and rows where it's
    NULL are read too. Reading a query, put ``:partition_start`` and
    ``:partition_end`` where the range belongs (for example ``WHERE
    order_id BETWEEN :partition_start AND :partition_end``) and set
    ``lower`` and ``upper``.
    """

    model_config = ConfigDict(extra="forbid")

    parts: int = Field(ge=2, le=32)
    column: str | None = Field(default=None, min_length=1)
    lower: int | None = None
    upper: int | None = None

    @model_validator(mode="after")
    def check_bounds(self) -> Self:
        if (self.lower is None) != (self.upper is None):
            raise ValueError("Set both 'lower' and 'upper', or neither.")

        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise ValueError("'lower' can't be greater than 'upper'.")
        return self


class SQLReadOptions(BaseModel):
    """Fields of a read step that uses a SQL connection.

    Set one of ``query``, ``query_file`` (a ``.sql`` file, relative to the
    pipeline file) or ``table`` (``name`` or ``schema.name``). Queries take
    ``:name`` placeholders filled from ``params``. ``args`` go to
    ``pandas.read_sql``. ``partition`` splits a large read into ranges that
    are read at the same time.
    """

    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, min_length=1)
    query_file: str | None = Field(default=None, min_length=1)
    table: str | None = Field(default=None, min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    args: dict[str, Any] = Field(default_factory=dict)
    partition: SQLPartition | None = None

    @model_validator(mode="after")
    def check_source(self) -> Self:
        sources = [self.query, self.query_file, self.table]

        if sum(source is not None for source in sources) != 1:
            raise ValueError("Set exactly one of 'query', 'query_file' or 'table'.")

        if self.params and self.table is not None:
            raise ValueError("'params' can only be used with a query.")

        if self.table is not None:
            split_table(self.table)

        if self.partition is not None:
            self.check_partition(self.partition)
        return self

    def check_partition(self, partition: SQLPartition) -> None:
        if self.table is not None:
            if partition.column is None:
                raise ValueError("Partitioning a table needs 'partition.column'.")
            return

        if partition.column is not None:
            raise ValueError(
                "'partition.column' only applies to tables; put :partition_start "
                "and :partition_end in the query instead."
            )

        if partition.lower is None:
            raise ValueError(
                "Partitioning a query needs 'partition.lower' and 'partition.upper'."
            )

        reserved = sorted(set(self.params) & set(PARTITION_PLACEHOLDERS))

        if reserved:
            raise ValueError(f"'params' can't set {', '.join(reserved)} here.")

        if self.query is not None:
            check_partition_placeholders(self.query)


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

    def check(self) -> str:
        import sqlalchemy as sa  # noqa: PLC0415

        with self.engine.connect() as connection:
            connection.execute(sa.select(sa.literal(1)))

        return "connected"

    @property
    def engine(self) -> sa.Engine:
        if self._engine is None:
            raise ExecutionError(f"Connection '{self.name}' is not open.")
        return self._engine

    def describe(self, options: SQLReadOptions | SQLWriteOptions) -> str:
        if isinstance(options, SQLWriteOptions):
            return f"table {options.table} (if it exists: {options.if_exists})"
        if options.query_file is not None:
            source = f"the query in {options.query_file}"
        elif options.table is not None:
            source = f"table {options.table}"
        else:
            source = "a query"

        partition = options.partition

        if partition is None:
            return source

        by = f" by {partition.column}" if partition.column else ""
        return f"{source} in {partition.parts} parallel parts{by}"

    def prepare_read(self, options: SQLReadOptions) -> SQLReadOptions:
        if options.query_file is None:
            return options

        path = self.base_dir / options.query_file

        try:
            query = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ValueError(
                f"Query file '{options.query_file}' not found (looked for {path})."
            ) from None

        if options.partition is not None:
            check_partition_placeholders(query)

        return options.model_copy(update={"query": query})

    def read(self, options: SQLReadOptions) -> pd.DataFrame:
        if options.partition is not None:
            return self._read_partitioned(options, options.partition)

        if options.query is not None:
            return self._read_query(options.query, options.params, options.args)

        if options.table is not None:
            schema, table = split_table(options.table)

            with self.engine.connect() as connection:
                return pd.read_sql_table(
                    table,
                    connection,
                    schema=schema,
                    **options.args,
                )

        raise ExecutionError("A SQL read needs a 'query' or a 'table'.")

    def _read_query(
        self,
        query: str,
        params: dict[str, Any],
        args: dict[str, Any],
    ) -> pd.DataFrame:
        import sqlalchemy as sa  # noqa: PLC0415

        with self.engine.connect() as connection:
            return pd.read_sql(
                sa.text(escape_non_code_colons(query)),
                connection,
                params=params,
                **args,
            )

    def _read_partitioned(
        self,
        options: SQLReadOptions,
        partition: SQLPartition,
    ) -> pd.DataFrame:
        """Read each range on its own connection, all at once, then combine."""
        extra_jobs: list[tuple[str, dict[str, Any]]] = []
        lower, upper = partition.lower, partition.upper

        if options.table is not None:
            source, column = self._quoted_names(options.table, partition.column or "")

            if lower is None or upper is None:
                lower, upper = self._column_range(source, column)

            if lower is None or upper is None:
                # Empty table, or no values to split by: read it whole.
                return self.read(options.model_copy(update={"partition": None}))

            # Names come from the pipeline file, quoted by the database's own
            # rules; values are bound parameters.
            query = (
                f"SELECT * FROM {source} "  # noqa: S608
                f"WHERE {column} BETWEEN :partition_start AND :partition_end"
            )
            params: dict[str, Any] = {}
            nulls = f"SELECT * FROM {source} WHERE {column} IS NULL"  # noqa: S608
            extra_jobs.append((nulls, {}))
        else:
            query, params = options.query or "", options.params

        if lower is None or upper is None:
            raise ExecutionError("A partitioned read needs 'lower' and 'upper'.")

        jobs = [
            (query, {**params, "partition_start": start, "partition_end": end})
            for start, end in split_range(lower, upper, partition.parts)
        ]
        jobs += extra_jobs

        with ThreadPoolExecutor(len(jobs), thread_name_prefix="dagcraft-sql") as pool:
            frames = list(
                pool.map(
                    lambda job: self._read_query(job[0], job[1], options.args),
                    jobs,
                )
            )

        # The NULL part's key column is all-empty (object dtype); infer types
        # again so the result matches an unpartitioned read.
        return pd.concat(frames, ignore_index=True).infer_objects()

    def _quoted_names(self, table: str, column: str) -> tuple[str, str]:
        """``schema.table`` and ``column``, quoted for this database."""
        preparer = self.engine.dialect.identifier_preparer
        schema, name = split_table(table)
        source = preparer.quote(name)

        if schema is not None:
            source = f"{preparer.quote_schema(schema)}.{source}"
        return source, preparer.quote(column)

    def _column_range(self, source: str, column: str) -> tuple[int | None, int | None]:
        import sqlalchemy as sa  # noqa: PLC0415

        with self.engine.connect() as connection:
            # Names quoted by the database's own rules, as above.
            bounds = f"SELECT MIN({column}), MAX({column}) FROM {source}"  # noqa: S608
            lower, upper = connection.execute(sa.text(bounds)).one()

        return whole_number(lower, column), whole_number(upper, column)

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

    A relative SQLite path is relative to the pipeline file's directory, and
    the folder for a new SQLite file is created.
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

        if url.get_backend_name() == "sqlite" and url.database not in (
            None,
            "",
            ":memory:",
        ):
            database = self.base_dir / (url.database or "")
            # SQLite creates the file but not its folder.
            database.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(database))

        if url.get_backend_name() == "sqlite" and url.database in (
            None,
            "",
            ":memory:",
        ):
            return sa.create_engine(url)

        return sa.create_engine(url, pool_pre_ping=True, max_overflow=POOL_OVERFLOW)


def escape_non_code_colons(query: str) -> str:
    r"""Escape colons in comments, strings and quoted names as ``\:``.

    SQLAlchemy reads ``:name`` as a parameter anywhere in a query, even in
    ``-- comments`` and ``'string literals'``, where the database doesn't
    see a placeholder. Escaping those colons leaves parameters only in code.
    """
    pieces = []
    position = 0
    length = len(query)

    while position < length:
        character = query[position]

        if query.startswith("--", position):
            end = query.find("\n", position)
            end = length if end == -1 else end
        elif query.startswith("/*", position):
            end = query.find("*/", position + 2)
            end = length if end == -1 else end + 2
        elif character in "'\"[":
            end = closing_quote(query, position, "]" if character == "[" else character)
        else:
            pieces.append(character)
            position += 1
            continue

        pieces.append(query[position:end].replace(":", "\\:"))
        position = end

    return "".join(pieces)


def closing_quote(query: str, start: int, quote: str) -> int:
    """Index just past the quote closing the one at ``start``.

    A doubled quote inside (``'it''s'``) is part of the text.
    """
    position = start + 1

    while position < len(query):
        if query[position] == quote:
            if query.startswith(quote * 2, position):
                position += 2
                continue
            return position + 1
        position += 1

    return len(query)


def check_partition_placeholders(query: str) -> None:
    """A partitioned query must use both :partition_start and :partition_end."""
    code = escape_non_code_colons(query)
    missing = [
        name
        for name in PARTITION_PLACEHOLDERS
        if not re.search(rf"(?<![\\\w:]):{name}\b", code)
    ]

    if missing:
        placeholders = " and ".join(f":{name}" for name in missing)
        raise ValueError(f"A partitioned query must use {placeholders}.")


def split_range(lower: int, upper: int, parts: int) -> list[tuple[int, int]]:
    """Split ``lower..upper`` (inclusive) into up to ``parts`` similar ranges."""
    total = upper - lower + 1
    parts = min(parts, total)
    size, extra = divmod(total, parts)
    ranges = []
    start = lower

    for index in range(parts):
        end = start + size - 1 + (1 if index < extra else 0)
        ranges.append((start, end))
        start = end + 1

    return ranges


def whole_number(value: Any, column: str) -> int | None:
    """``value`` as an int, for a partition boundary."""
    if value is None:
        return None

    if isinstance(value, int) and not isinstance(value, bool):
        return value

    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)

    raise ExecutionError(
        f"Partition column {column} must hold whole numbers, "
        f"not {type(value).__name__}."
    )


def split_table(table: str) -> tuple[str | None, str]:
    """Split ``name`` or ``schema.name`` into its schema and name."""
    match table.split("."):
        case [name] if name:
            return None, name
        case [schema, name] if schema and name:
            return schema, name

    raise ValueError(f"Table '{table}' should be written as 'name' or 'schema.name'.")
