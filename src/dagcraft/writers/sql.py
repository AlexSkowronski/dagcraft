"""
Writing a table to a SQL database, in one transaction.
"""

import pandas as pd

from dagcraft.config.writers import SQLWriteOptions
from dagcraft.connections.sql import SQLConnection
from dagcraft.connections.sql.names import split_table
from dagcraft.registry import register_writer
from dagcraft.writers.base import Writer


@register_writer(SQLConnection)
class SQLWriter(Writer):
    """
    Writes a DataFrame to ``table``, replacing or appending as configured.

    The write runs in one transaction, so a failure leaves the table as it
    was.
    """

    options_model = SQLWriteOptions
    options: SQLWriteOptions

    def prepare(self, connection: SQLConnection) -> None:
        split_table(self.options.table)

    def describe(self) -> str:
        return f"table {self.options.table} (if it exists: {self.options.if_exists})"

    def write(self, connection: SQLConnection, data: pd.DataFrame) -> None:
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
