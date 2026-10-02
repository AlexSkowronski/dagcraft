from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dagcraft.config import PipelineConfig
from dagcraft.exceptions import ConfigError
from dagcraft.executor import Executor
from dagcraft.graph import (
    CompiledGraph,
    compile_graph,
)
from dagcraft.runtime import PipelineResult


class Pipeline:
    def __init__(
        self,
        config: PipelineConfig,
    ):
        self.config = config
        self.graph: CompiledGraph = compile_graph(config)

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

        return cls.from_dict(raw)

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
    ) -> Pipeline:
        try:
            parsed = PipelineConfig.model_validate(config)

        except ValidationError as exc:
            raise ConfigError(str(exc)) from exc

        return cls(parsed)

    def validate(self) -> bool:
        # Configuration validation occurs through
        # Pydantic, and graph validation occurs when
        # the Pipeline is constructed.
        return True

    def run(
        self,
        logger: logging.Logger | None = None,
    ) -> PipelineResult:
        executor = Executor(
            config=self.config,
            graph=self.graph,
            logger=logger,
        )

        return executor.run()
