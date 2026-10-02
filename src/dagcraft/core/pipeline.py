from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dagcraft.core.compiler import CompiledPipeline, compile_pipeline
from dagcraft.core.config import PipelineConfig, format_validation_error, load_yaml
from dagcraft.core.executor import Executor
from dagcraft.core.runtime import ConnectionCheck, PipelineResult, PlannedStep
from dagcraft.exceptions import ConfigError, PipelineError

logger = logging.getLogger(__name__)


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

    def plan(self) -> list[PlannedStep]:
        """The steps in the order they would run, without running them.

        Everything is already checked when the pipeline is created, so a
        pipeline you can plan is one you can run.
        """
        return [
            PlannedStep(
                id=step_id,
                description=self.compiled.steps[step_id].describe(),
                inputs=dict(self.compiled.steps[step_id].config.inputs),
            )
            for step_id in self.compiled.graph.order
        ]

    def connections_in_use(self) -> list[str]:
        """Names of the connections the steps use, in the order they're used."""
        names: list[str] = []

        for step_id in self.compiled.graph.order:
            name = getattr(self.compiled.steps[step_id].config, "connection", None)

            if isinstance(name, str) and name not in names:
                names.append(name)

        return names

    def check_connections(self) -> list[ConnectionCheck]:
        """Open each connection the steps use and prove it works.

        Each connection does one cheap real operation, such as listing a
        folder or running ``SELECT 1``, so problems with credentials,
        permissions, network or drivers show up without running any steps.
        A failure is reported in the result rather than raised.
        """
        checks = []

        for name in self.connections_in_use():
            connection = self.compiled.connections[name]
            connection_type = self.config.connections.get(name, {}).get("type", "local")

            try:
                connection.open()
                message = connection.check()
            except Exception as exc:
                logger.debug("Checking connection '%s' failed", name, exc_info=True)
                checks.append(ConnectionCheck(name, connection_type, False, str(exc)))
            else:
                checks.append(ConnectionCheck(name, connection_type, True, message))
            finally:
                with contextlib.suppress(Exception):
                    connection.close()

        return checks

    def run(
        self,
        logger: logging.Logger | None = None,
        fail_fast: bool = False,
        run_id: str | None = None,
    ) -> PipelineResult:
        """Run the pipeline and return the outcome of every step.

        When a step fails, the steps that depend on it are skipped and the
        rest still run; with ``fail_fast``, every later step is skipped.

        Raises ``PipelineError`` if any step fails. The error's ``result``
        has the per-step outcome, and the first failure's exception is
        chained.

        ``run_id`` identifies the run in logs and the result; by default a
        short random one is made. Pass your own to match an orchestrator's.
        """
        executor = Executor(
            pipeline=self.compiled,
            logger=logger,
            fail_fast=fail_fast,
            run_id=run_id,
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
