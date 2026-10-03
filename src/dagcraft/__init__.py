"""Config-driven DAG pipelines for Python.

    from dagcraft import Pipeline

    Pipeline.from_yaml("pipelines/daily_sales.yaml").run()

Everything you need to run pipelines, and to extend dagcraft with your own
steps, connections, readers, writers and formats, is importable from here.
"""

import logging
from importlib.metadata import PackageNotFoundError, version

from dagcraft.config import StepConfig
from dagcraft.connections import Connection, FileConnection, SQLConnection
from dagcraft.core.pipeline import Pipeline
from dagcraft.core.results import PipelineResult, StepStatus
from dagcraft.exceptions import (
    ConfigError,
    ExecutionError,
    PipelineError,
    RunError,
)
from dagcraft.formats import Format
from dagcraft.logs import configure_logging, get_logger
from dagcraft.readers import Reader
from dagcraft.registry import (
    register_connection,
    register_format,
    register_operation,
    register_reader,
    register_step,
    register_writer,
)
from dagcraft.steps import BaseStep
from dagcraft.timing import Timer
from dagcraft.writers import Writer

# Libraries leave logging configuration to the application.
logging.getLogger("dagcraft").addHandler(logging.NullHandler())

try:
    __version__ = version("dagcraft-pipelines")
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0+unknown"

__all__ = [
    "BaseStep",
    "ConfigError",
    "Connection",
    "ExecutionError",
    "FileConnection",
    "Format",
    "Pipeline",
    "PipelineError",
    "PipelineResult",
    "Reader",
    "RunError",
    "SQLConnection",
    "StepConfig",
    "StepStatus",
    "Timer",
    "Writer",
    "__version__",
    "configure_logging",
    "get_logger",
    "register_connection",
    "register_format",
    "register_operation",
    "register_reader",
    "register_step",
    "register_writer",
]
