"""
Doing several things at once in threads, such as downloading files.
"""

import contextvars
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any


def map_in_threads(
    function: Callable[[Any], Any],
    items: Sequence[Any],
    *,
    workers: int,
    name: str = "dagcraft",
) -> list[Any]:
    """
    ``function`` applied to each of ``items``, up to ``workers`` at once.

    Results come back in the order of ``items``. Each thread gets a copy of
    the caller's context, so log messages still name the run and step. With
    one worker or one item, everything runs in the calling thread. The first
    error is raised once the others have finished.
    """
    if workers <= 1 or len(items) <= 1:
        return [function(item) for item in items]

    with ThreadPoolExecutor(min(workers, len(items)), thread_name_prefix=name) as pool:
        futures = [
            pool.submit(contextvars.copy_context().run, function, item)
            for item in items
        ]
        return [future.result() for future in futures]
