"""
Writing a table to a SQL database, in one transaction.
"""

from typing import Any

from dagcraft.config.writers import SQLWriteOptions
from dagcraft.connections.sql import SQLConnection
from dagcraft.connections.sql.names import split_table
from dagcraft.data import require_table
from dagcraft.logs import get_logger
from dagcraft.registry import register_writer
from dagcraft.writers.base import Writer
from dagcraft.writers.sql.upsert import upsert

logger = get_logger(__name__)


@register_writer(SQLConnection)
class SQLWriter(Writer):
    """
    Writes a DataFrame to ``table``: replacing, appending or upserting.

    The write runs in one transaction, so a failure leaves the table as it
    was.
    """

    options_model = SQLWriteOptions
    options: SQLWriteOptions

    def prepare(self, connection: SQLConnection) -> None:
        split_table(self.options.table)

    def describe(self) -> str:
        if_exists = self.options.if_exists

        if if_exists == "upsert":
            if_exists = f"upsert by {', '.join(self.options.keys)}"

        return f"table {self.options.table} (if it exists: {if_exists})"

    def write(self, connection: SQLConnection, data: Any) -> None:
        data = require_table(data, "A SQL table")

        if self.options.if_exists == "upsert":
            counts = upsert(
                connection.engine,
                data,
                self.options.table,
                self.options.keys,
                self.options.args,
            )
            logger.info(
                "upserted into %s: %s rows replaced, %s added",
                self.options.table,
                f"{counts.replaced:,}",
                f"{counts.added:,}",
            )
            return

        schema, table = split_table(self.options.table)
        args = {"index": False, **self.options.args}

        with connection.engine.begin() as transaction:
            data.to_sql(
                table,
                transaction,
                schema=schema,
                if_exists=self.options.if_exists,
                **args,
            )
