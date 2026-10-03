"""Measuring how long things take."""

import functools
import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any, Self


class Timer:
    """Measures elapsed wall-clock time, as a context manager or a decorator.

    As a context manager, ``elapsed`` grows while the block runs and is fixed
    once it ends::

        with Timer() as timer:
            load()
        print(timer.elapsed)

    As a decorator, every call is timed separately. Give a ``label`` and a
    ``logger`` to log each duration::

        @Timer("load", logger=logging.getLogger(__name__))
        def load(): ...
    """

    def __init__(
        self,
        label: str = "",
        logger: logging.Logger | logging.LoggerAdapter[Any] | None = None,
        level: int = logging.INFO,
    ) -> None:
        self.label = label
        self.logger = logger
        self.level = level
        self._start: float | None = None
        self._end: float | None = None

    def __enter__(self) -> Self:
        self._start = perf_counter()
        self._end = None
        return self

    def __exit__(self, *_: object) -> None:
        self._end = perf_counter()

        if self.logger is not None:
            self.logger.log(
                self.level,
                "%s took %.3fs",
                self.label or "block",
                self.elapsed,
            )

    def __call__(self, function: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(function)
        def timed(*args: Any, **kwargs: Any) -> Any:
            # A fresh timer per call, so overlapping calls don't share one.
            with Timer(self.label or function.__qualname__, self.logger, self.level):
                return function(*args, **kwargs)

        return timed

    @property
    def elapsed(self) -> float:
        """Seconds since the timer started; fixed once it has stopped."""
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else perf_counter()
        return end - self._start
