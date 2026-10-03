"""Reading from SQL databases: a query, a ``.sql`` file or a whole table."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from dagcraft.config.readers import SQLPartition, SQLReadOptions
from dagcraft.connections.sql import SQLConnection
from dagcraft.connections.sql.names import split_table
from dagcraft.logs import get_logger
from dagcraft.readers.base import Reader
from dagcraft.readers.sql.partitions import (
    Part,
    range_parts,
    read_parts,
    table_parts,
)
from dagcraft.readers.sql.query import load_query_file, read_query, read_table
from dagcraft.readers.sql.query_text import check_partition_placeholders
from dagcraft.registry import register_reader

if TYPE_CHECKING:
    import sqlalchemy as sa

logger = get_logger(__name__)


@register_reader(SQLConnection)
class SQLReader(Reader):
    """Reads a query, a query file or a table from any SQL connection."""

    options_model = SQLReadOptions
    options: SQLReadOptions

    def __init__(self, options: SQLReadOptions) -> None:
        super().__init__(options)
        # The query text; for query_file, filled in by prepare.
        self.query = options.query

    def prepare(self, connection: SQLConnection) -> None:
        if self.options.table is not None:
            split_table(self.options.table)

        if self.options.query_file is not None:
            self.query = load_query_file(connection.base_dir, self.options.query_file)

        if self.options.partition is not None and self.query is not None:
            check_partition_placeholders(self.query)

    def describe(self) -> str:
        if self.options.query_file is not None:
            source = f"the query in {self.options.query_file}"
        elif self.options.table is not None:
            source = f"table {self.options.table}"
        else:
            source = "a query"

        partition = self.options.partition

        if partition is None:
            return source

        by = f" by {partition.column}" if partition.column else ""
        return f"{source} in {partition.parts} parallel parts{by}"

    def read(self, connection: SQLConnection) -> pd.DataFrame:
        if self.options.partition is not None:
            return self._read_partitioned(connection, self.options.partition)

        if self.query is not None:
            return read_query(
                connection.engine,
                self.query,
                self.options.params,
                self.options.args,
            )

        return read_table(
            connection.engine, self.options.table or "", self.options.args
        )

    def _read_partitioned(
        self,
        connection: SQLConnection,
        partition: SQLPartition,
    ) -> pd.DataFrame:
        engine = connection.engine
        parts = self._parts(engine, partition)

        if parts is None:
            logger.info(
                "%s has no %s values to split by; reading it whole",
                self.options.table,
                partition.column,
            )
            return read_table(engine, self.options.table or "", self.options.args)

        logger.info("reading in %d parts at once", len(parts))
        return read_parts(engine, parts, self.options.args)

    def _parts(self, engine: sa.Engine, partition: SQLPartition) -> list[Part] | None:
        """The queries to run, or ``None`` if a table should be read whole."""
        if self.options.table is not None:
            return table_parts(engine, self.options.table, partition)

        # The options model makes sure a partitioned query has both bounds.
        return range_parts(
            self.query or "",
            self.options.params,
            partition.lower or 0,
            partition.upper or 0,
            partition.parts,
        )
