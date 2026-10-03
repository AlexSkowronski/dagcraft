"""What a pipeline file can say: pydantic models for every part of it.

The models only describe and validate the file. The components that act on
them (connections, readers, writers, steps) live in their own packages and
point at their model through a ``config_model`` or ``options_model``
attribute.
"""

from dagcraft.config.pipeline import PipelineConfig, PipelineMeta
from dagcraft.config.steps import StepConfig
from dagcraft.config.validation import format_validation_error

__all__ = [
    "PipelineConfig",
    "PipelineMeta",
    "StepConfig",
    "format_validation_error",
]
