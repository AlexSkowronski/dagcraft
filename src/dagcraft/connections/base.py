from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from dagcraft.exceptions import ExecutionError


class Connection:
    """Base class for connection types.

    A connection is created when the pipeline is compiled, opened the first
    time a step uses it during a run, and closed when the run ends.

    Subclasses set ``config_model`` to validate their entry in the
    ``connections`` block, and ``read_options`` / ``write_options`` to
    validate the remaining fields of read and write steps that use them.
    Leaving one as ``None`` means the connection cannot be read from or
    written to.
    """

    config_model: ClassVar[type[BaseModel]]
    read_options: ClassVar[type[BaseModel] | None] = None
    write_options: ClassVar[type[BaseModel] | None] = None

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        self.name = name
        self.config = config
        self.base_dir = base_dir

    def open(self) -> None:
        """Acquire resources, such as clients or engines."""

    def close(self) -> None:
        """Release anything acquired in ``open``."""

    def read(self, options: Any) -> Any:
        raise NotImplementedError

    def write(self, data: Any, options: Any) -> None:
        raise NotImplementedError


def read_variable(variable: str, connection: str, purpose: str) -> str:
    """Return an environment variable, or raise if it's unset or empty."""
    value = os.environ.get(variable)

    if not value:
        raise ExecutionError(
            f"Connection '{connection}' reads its {purpose} from the "
            f"environment variable '{variable}', which is not set."
        )
    return value
