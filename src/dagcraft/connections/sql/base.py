"""
The base class for connections to SQL databases.

Reading and writing go through SQLAlchemy, so they work the same for every
database. Each connection type only decides how to build the engine: which
driver, which URL, how to sign in. Supporting another database (Postgres
with Entra ID sign-in, say) means one more subclass.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from dagcraft.connections.base import Connection
from dagcraft.extras import require_extra

if TYPE_CHECKING:
    import sqlalchemy as sa

# Extra pooled connections allowed beyond the usual 5, for partitioned reads
# and parallel steps.
POOL_OVERFLOW = 40


class SQLConnection(Connection):
    """
    A SQL database, reached through a SQLAlchemy engine.

    Subclasses implement ``create_engine``. ``extra`` names the package
    extra that provides the dependencies.
    """

    extra: ClassVar[str] = "sql"

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        require_extra("sqlalchemy", extra=self.extra)
        super().__init__(name, config, base_dir)
        self._engine: sa.Engine | None = None

    @abstractmethod
    def create_engine(self) -> sa.Engine:
        """
        Build the engine this connection reads and writes through.
        """

    def open(self) -> None:
        self._engine = self.create_engine()

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    @property
    def engine(self) -> sa.Engine:
        """
        The open engine; raises if the connection isn't open.
        """
        if self._engine is None:
            raise self.not_open()
        return self._engine

    def check(self) -> str:
        import sqlalchemy as sa  # noqa: PLC0415

        with self.engine.connect() as connection:
            connection.execute(sa.select(sa.literal(1)))

        return "connected"
