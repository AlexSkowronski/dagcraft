"""Proving a connection works, without running any steps."""

import contextlib

from dagcraft.connections import Connection
from dagcraft.core.results import ConnectionCheck
from dagcraft.logs import get_logger

logger = get_logger(__name__)


def check_connection(
    name: str, type_name: str, connection: Connection
) -> ConnectionCheck:
    """Open ``connection``, run its check, and close it again.

    A failure is reported in the result rather than raised.
    """
    try:
        connection.open()
        message = connection.check()
    except Exception as exc:
        logger.debug("Checking connection '%s' failed", name, exc_info=True)
        return ConnectionCheck(name, type_name, ok=False, message=str(exc))
    else:
        return ConnectionCheck(name, type_name, ok=True, message=message)
    finally:
        with contextlib.suppress(Exception):
            connection.close()
