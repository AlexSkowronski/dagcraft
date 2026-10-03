"""
Where steps run: worker threads, or straight away in the calling thread.
"""

import contextvars
from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from typing import Any


class InlineExecutor(Executor):
    """
    Runs each submitted call straight away, in the calling thread.
    """

    def submit(
        self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any
    ) -> Future[Any]:
        future: Future[Any] = Future()
        future.set_result(fn(*args, **kwargs))
        return future


def worker_pool(max_workers: int) -> Executor:
    """
    Threads for running up to ``max_workers`` steps at once.

    With one worker, steps run in the calling thread instead, which keeps
    tracebacks and debugging simple.
    """
    if max_workers == 1:
        return InlineExecutor()
    return ThreadPoolExecutor(max_workers, thread_name_prefix="dagcraft")


def submit_in_context(
    pool: Executor,
    function: Callable[..., Any],
    *args: Any,
) -> Future[Any]:
    """
    Submit ``function`` to run with a copy of the current context.

    Threads don't inherit context variables, which is how log messages know
    their run and step.
    """
    return pool.submit(contextvars.copy_context().run, function, *args)
