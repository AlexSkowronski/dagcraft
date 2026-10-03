"""
The ``Pipeline`` class: load a pipeline file, then plan, check or run it.
"""

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import ValidationError

from dagcraft.config import PipelineConfig, RunOptions, format_validation_error
from dagcraft.core.checks import check_connection
from dagcraft.core.compiler import CompiledPipeline, compile_pipeline
from dagcraft.core.executor import Executor
from dagcraft.core.results import ConnectionCheck, PipelineResult, PlannedStep
from dagcraft.exceptions import ConfigError, RunError
from dagcraft.yaml_loader import load_yaml


class Pipeline:
    """
    A checked pipeline, ready to plan, check or run.

    Usually created with ``Pipeline.from_yaml(path)``. Everything is checked
    when the pipeline is created, so a pipeline that exists is one that can
    run; ``run`` can then be called any number of times.
    """

    def __init__(
        self,
        config: PipelineConfig,
        base_dir: str | Path | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        """
        Compile ``config``.

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

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        params: dict[str, Any] | None = None,
    ) -> Self:
        """
        Load and compile a pipeline file. Relative paths are relative to it.
        """
        path = Path(path)

        try:
            raw = load_yaml(path.read_text(encoding="utf-8"))
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
    ) -> Self:
        """
        Compile a pipeline from a dict shaped like a pipeline file.
        """
        try:
            parsed = PipelineConfig.model_validate(config)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid pipeline: {format_validation_error(exc)}"
            ) from exc

        return cls(parsed, base_dir=base_dir, params=params)

    @property
    def name(self) -> str:
        """
        The pipeline's name, from its file.
        """
        return self.compiled.name

    @property
    def params(self) -> dict[str, Any]:
        """
        The params in effect: the file's, with any overrides applied.
        """
        return self.compiled.params

    @property
    def max_workers(self) -> int:
        """
        How many independent steps the file lets run at once.
        """
        return self.config.pipeline.max_workers

    def plan(self) -> list[PlannedStep]:
        """
        The steps in the order they would run, without running them.
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
        """
        Names of the connections the steps use, in the order they're used.
        """
        names: list[str] = []

        for step_id in self.compiled.graph.order:
            name = self.compiled.steps[step_id].connection_name()

            if name is not None and name not in names:
                names.append(name)

        return names

    def check_connections(self) -> list[ConnectionCheck]:
        """
        Open each connection the steps use and prove it works.

        Each connection does one cheap real operation, such as listing a
        folder or running ``SELECT 1``, so problems with credentials,
        permissions, network or drivers show up without running any steps.
        A failure is reported in the result rather than raised.
        """
        return [
            check_connection(
                name,
                self.compiled.connection_types[name],
                self.compiled.connections[name],
            )
            for name in self.connections_in_use()
        ]

    def run(
        self,
        *,
        fail_fast: bool = False,
        run_id: str | None = None,
        keep_outputs: bool = True,
        max_workers: int | None = None,
    ) -> PipelineResult:
        """
        Run the pipeline and return the outcome of every step.

        When a step fails, the steps that depend on it are skipped and the
        rest still run; with ``fail_fast``, every later step is skipped.
        Raises ``RunError`` if any step fails: its ``result`` has the
        per-step outcome, and the first failure's exception is chained.

        ``run_id`` identifies the run in logs and the result; by default a
        short random one is made. Pass your own to match an orchestrator's.

        Each step's output is kept on the result (``result.output(id)``).
        With ``keep_outputs=False``, an output is dropped as soon as every
        step that uses it has finished, which saves memory on large data.

        ``max_workers`` overrides the pipeline file's ``max_workers``: how
        many independent steps may run at once, each in its own thread.

        The options are checked by ``RunOptions``, as the command line's
        are; invalid ones raise ``ConfigError``.
        """
        options = RunOptions.parse(
            fail_fast=fail_fast,
            run_id=run_id,
            keep_outputs=keep_outputs,
            max_workers=max_workers,
        )

        result = Executor(
            self.compiled,
            fail_fast=options.fail_fast,
            run_id=options.run_id,
            keep_outputs=options.keep_outputs,
            max_workers=options.max_workers or self.max_workers,
        ).run()

        if not result.success:
            # A run fails only when a step does, so there is a first failure.
            first_failure = result.failed_steps[0]
            raise RunError.from_result(result) from first_failure.exception

        return result
