import logging
from importlib.metadata import PackageNotFoundError, version

from dagcraft.connections import Connection, FileConnection, FsspecConnection
from dagcraft.core.pipeline import Pipeline
from dagcraft.core.runtime import PipelineResult
from dagcraft.exceptions import ConfigError, DagcraftError, PipelineError
from dagcraft.formats import Format
from dagcraft.registry import (
    register_connection,
    register_format,
    register_operation,
    register_step,
)
from dagcraft.steps import BaseStep, StepConfig

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
    "DagcraftError",
    "FileConnection",
    "Format",
    "FsspecConnection",
    "Pipeline",
    "PipelineError",
    "PipelineResult",
    "StepConfig",
    "__version__",
    "register_connection",
    "register_format",
    "register_operation",
    "register_step",
]
