"""The ``sql`` connection type: any database SQLAlchemy supports, by URL.

Requires the ``sql`` extra (``pip install 'dagcraft-pipelines[sql]'``) plus a
driver for your database, such as ``psycopg`` for Postgres. SQLite works out
of the box.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dagcraft.config.connections import SQLConfig
from dagcraft.connections.sql.base import POOL_OVERFLOW, SQLConnection
from dagcraft.registry import register_connection

if TYPE_CHECKING:
    import sqlalchemy as sa

IN_MEMORY_SQLITE = (None, "", ":memory:")


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

        url = sa.make_url(self.config.url.get_secret_value())

        if url.get_backend_name() != "sqlite":
            return sa.create_engine(url, pool_pre_ping=True, max_overflow=POOL_OVERFLOW)

        if url.database in IN_MEMORY_SQLITE:
            return sa.create_engine(url)

        return sa.create_engine(
            url.set(database=str(sqlite_file(self.base_dir, url.database or ""))),
            pool_pre_ping=True,
            max_overflow=POOL_OVERFLOW,
        )


def sqlite_file(base_dir: Path, database: str) -> Path:
    """The SQLite file's full path, with its folder created.

    SQLite creates a missing database file, but not its folder.
    """
    path = base_dir / database
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
