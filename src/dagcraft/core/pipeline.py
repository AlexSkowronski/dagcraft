from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dagcraft.core.compiler import CompiledPipeline, compile_pipeline
from dagcraft.core.config import PipelineConfig, format_validation_error, load_yaml
from dagcraft.core.executor import Executor
from dagcraft.core.runtime import PipelineResult
from dagcraft.exceptions import ConfigError, PipelineError


class Pipeline:
    def __init__(
        self,
        config: PipelineConfig,
        base_dir: str | Path | None = None,
        params: dict[str, Any] | None = None,
    ):
        """Compile ``config``.

        ``base_dir`` is where relative paths in the config are resolved from;
        it defaults to the current directory, or the file's directory when
        loaded with ``from_yaml``. ``params`` override the file's params.
        """
        self.config = config
        self.base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
        self.compiled: CompiledPipeline = compile_pipeline(
            config,
            self.base_dir,
            params,
        )

    @property
    def params(self) -> dict[str, Any]:
        """The params in effect: the file's, with any overrides applied."""
        return self.compiled.params

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        params: dict[str, Any] | None = None,
    ) -> Pipeline:
        path = Path(path)

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                raw = load_yaml(file)

        except OSError as exc:
            raise ConfigError(f"Could not read pipeline file: {path}") from exc

        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in pipeline file {path}: {exc}") from exc

        return cls.from_dict(raw, base_dir=path.resolve().parent, params=params)

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
        base_dir: str | Path | None = None,
        params: dict[str, Any] | None = None,
    ) -> Pipeline:
        try:
            parsed = PipelineConfig.model_validate(config)

        except ValidationError as exc:
            raise ConfigError(
                f"Invalid pipeline: {format_validation_error(exc)}"
            ) from exc

        return cls(parsed, base_dir=base_dir, params=params)

    def validate(self) -> bool:
        # Everything is checked when the pipeline is compiled in __init__:
        # the file structure, each step and connection against its registered
        # type, references to operations and connections, and the graph.
        return True

    def run(
        self,
        logger: logging.Logger | None = None,
        fail_fast: bool = False,
    ) -> PipelineResult:
        """Run the pipeline and return the outcome of every step.

        When a step fails, the steps that depend on it are skipped and the
        rest still run; with ``fail_fast``, every later step is skipped.

        Raises ``PipelineError`` if any step fails. The error's ``result``
        has the per-step outcome, and the first failure's exception is
        chained.
        """
        executor = Executor(
            pipeline=self.compiled,
            logger=logger,
            fail_fast=fail_fast,
        )

        result = executor.run()
        failed = result.failed_steps

        if failed:
            first, others = failed[0], failed[1:]
            message = (
                f"Pipeline '{result.name}' failed at step '{first.id}': {first.error}"
            )

            if others:
                names = ", ".join(step.id for step in others)
                message += f" (also failed: {names})"

            raise PipelineError(message, result) from first.exception

        return result
