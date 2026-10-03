"""
Logging for pipeline runs.

Every dagcraft module logs through ``get_logger(__name__)``. While a run is
in progress, each message is prefixed with the pipeline and run ID, and with
the step when one is running (``[sales a1b2c3d4] orders: ...``), and the
same values are attached to each record as ``pipeline``, ``run_id`` and
``step`` for log handlers that store fields. The run and step are tracked
with context variables, so nothing has to pass a logger around.

dagcraft only creates log records. Showing them is up to the application:
``configure_logging`` is a quick way to print them, which the command line
uses; otherwise configure the ``dagcraft`` logger as you would any other.
"""

import contextvars
import logging
from collections.abc import Generator, MutableMapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pandas as pd

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class RunInfo:
    """
    The run that log messages belong to.
    """

    pipeline: str
    run_id: str


_run: contextvars.ContextVar[RunInfo | None] = contextvars.ContextVar(
    "dagcraft_run", default=None
)
_step: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "dagcraft_step", default=None
)


class RunLogger(logging.LoggerAdapter[logging.Logger]):
    """
    Adds the current run and step to each message and record.
    """

    def process(
        self,
        msg: Any,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[Any, MutableMapping[str, Any]]:
        run, step = _run.get(), _step.get()
        prefix = ""

        if run is not None:
            prefix = f"[{run.pipeline} {run.run_id}] "
        if step is not None:
            prefix += f"{step}: "

        context = {
            "pipeline": run.pipeline if run else "",
            "run_id": run.run_id if run else "",
            "step": step or "",
        }
        kwargs["extra"] = {**context, **kwargs.get("extra", {})}
        return f"{prefix}{msg}", kwargs


def get_logger(name: str) -> RunLogger:
    """
    A logger whose messages carry the current run and step.
    """
    return RunLogger(logging.getLogger(name))


@contextmanager
def run_context(pipeline: str, run_id: str) -> Generator[None]:
    """
    Mark log messages logged inside the block as part of this run.
    """
    token = _run.set(RunInfo(pipeline, run_id))
    try:
        yield
    finally:
        _run.reset(token)


@contextmanager
def step_context(step_id: str) -> Generator[None]:
    """
    Mark log messages logged inside the block as coming from this step.
    """
    token = _step.set(step_id)
    try:
        yield
    finally:
        _step.reset(token)


def describe_data(value: Any) -> str:
    """
    A short description of a step's output for logs: its size, or its type.
    """
    if isinstance(value, pd.DataFrame):
        rows, columns = value.shape
        return f"{rows:,} rows x {columns:,} columns"

    if isinstance(value, dict) and value:
        return f"{len(value)} tables ({', '.join(map(str, value))})"

    if value is None:
        return "no output"

    return type(value).__name__


def configure_logging(level: int = logging.INFO) -> None:
    """
    Print log messages to the console with a timestamp and level.

    ``level`` applies to dagcraft's messages; other libraries only show
    warnings and errors, since some (such as the Azure SDK) log every request
    at INFO. For scripts and the command line: applications with their own
    logging setup should configure the ``dagcraft`` logger instead.
    """
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT, datefmt=DATE_FORMAT)
    logging.getLogger("dagcraft").setLevel(level)
