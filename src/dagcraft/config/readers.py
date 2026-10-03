"""
The fields of a read step, for each kind of connection.
"""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dagcraft.paths import has_wildcards

# Placeholders a partitioned query uses for the range each part reads.
PARTITION_PLACEHOLDERS = ("partition_start", "partition_end")


class FileReadOptions(BaseModel):
    """
    Reading from a file connection.

    Read one ``path``, every file matching a ``path`` with wildcards (``*``,
    ``?``, ``[...]``, ``**`` for any depth), or the files another step
    lists in its output, given as the step's ``paths`` input: a list, or a
    table with the paths in ``path_column``. ``format`` is inferred from
    the file extension unless set; ``args`` go to the format's reader
    (``pandas.read_csv`` and so on). With several files, ``source_column``
    names each row's (or document's) file, and up to ``parallel`` files
    are read at once.
    """

    model_config = ConfigDict(extra="forbid")

    path: str | None = Field(default=None, min_length=1)
    path_column: str | None = Field(default=None, min_length=1)
    format: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    source_column: str | None = Field(default=None, min_length=1)
    parallel: int = Field(default=4, ge=1, le=32)

    @model_validator(mode="after")
    def check_source_column(self) -> Self:
        """
        ``source_column`` only makes sense when several files are read.
        """
        one_file = self.path is not None and not has_wildcards(self.path)

        if self.source_column is not None and one_file:
            raise ValueError(
                "'source_column' only applies when several files are read: a "
                "'path' with wildcards, or a 'paths' input."
            )
        return self


class SQLPartition(BaseModel):
    """
    Split a read into ranges of a whole-number column, read at the same time.

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
        """
        ``lower`` and ``upper`` come as a pair, in order.
        """
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
    """
    Reading from a SQL connection.

    Set one of ``query``, ``query_file`` (a ``.sql`` file, relative to the
    folder you run from) or ``table`` (``name`` or ``schema.name``). Queries take
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
        """
        Exactly one source, and params only where there are placeholders.
        """
        sources = [self.query, self.query_file, self.table]

        if sum(source is not None for source in sources) != 1:
            raise ValueError("Set exactly one of 'query', 'query_file' or 'table'.")

        if self.params and self.table is not None:
            raise ValueError("'params' can only be used with a query.")

        if self.partition is not None:
            self._check_partition(self.partition)
        return self

    def _check_partition(self, partition: SQLPartition) -> None:
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
