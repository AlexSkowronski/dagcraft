from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dagcraft.compiler import CompiledPipeline, compile_pipeline
from dagcraft.config import PipelineConfig, format_validation_error
from dagcraft.exceptions import ConfigError
from dagcraft.executor import Executor
from dagcraft.runtime import PipelineResult


class Pipeline:
    def __init__(
        self,
        config: PipelineConfig,
        base_dir: str | Path | None = None,
    ):
        """Compile ``config``.

        ``base_dir`` is where relative paths in the config are resolved from;
        it defaults to the current directory, or the file's directory when
        loaded with ``from_yaml``.
        """
        self.config = config
        self.base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
        self.compiled: CompiledPipeline = compile_pipeline(config, self.base_dir)

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
    ) -> Pipeline:
        path = Path(path)

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                raw = yaml.safe_load(file)

        except OSError as exc:
            raise ConfigError(f"Could not read pipeline file: {path}") from exc

        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in pipeline file {path}: {exc}") from exc

        return cls.from_dict(raw, base_dir=path.resolve().parent)

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
        base_dir: str | Path | None = None,
    ) -> Pipeline:
        try:
            parsed = PipelineConfig.model_validate(config)

        except ValidationError as exc:
            raise ConfigError(
                f"Invalid pipeline: {format_validation_error(exc)}"
            ) from exc

        return cls(parsed, base_dir=base_dir)

    def validate(self) -> bool:
        # Everything is checked when the pipeline is compiled in __init__:
        # the file structure, each step and connection against its registered
        # type, references to operations and connections, and the graph.
        return True

    def run(
        self,
        logger: logging.Logger | None = None,
    ) -> PipelineResult:
        executor = Executor(
            pipeline=self.compiled,
            logger=logger,
        )

        return executor.run()
