"""
What a pipeline file (and a run) can say: pydantic models for each part.

The models only describe and validate the file. The components that act on
them (connections, readers, writers, steps) live in their own packages and
point at their model through a ``config_model`` or ``options_model``
attribute.
"""

from dagcraft.config.pipeline import PipelineConfig, PipelineMeta
from dagcraft.config.run import RunOptions
from dagcraft.config.steps import StepConfig
from dagcraft.config.validation import format_validation_error

__all__ = [
    "PipelineConfig",
    "PipelineMeta",
    "RunOptions",
    "StepConfig",
    "format_validation_error",
]
