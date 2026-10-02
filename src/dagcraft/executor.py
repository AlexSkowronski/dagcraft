from __future__ import annotations

import logging
import uuid
from time import perf_counter

# Importing steps registers the built-in step types.
from dagcraft import steps as _steps  # noqa: F401
from dagcraft.config import PipelineConfig
from dagcraft.graph import CompiledGraph
from dagcraft.registry import get_step
from dagcraft.runtime import (
    Artifact,
    ExecutionContext,
    PipelineResult,
    StepResult,
    StepStatus,
)


class Executor:
    def __init__(
        self,
        config: PipelineConfig,
        graph: CompiledGraph,
        logger: logging.Logger | None = None,
    ):
        self.config = config
        self.graph = graph

        self.logger = logger or logging.getLogger("dagcraft")

        self.step_configs = {step.id: step for step in config.steps}

    def run(self) -> PipelineResult:
        pipeline_start = perf_counter()

        context = ExecutionContext(
            run_id=str(uuid.uuid4()),
            logger=self.logger,
        )

        step_results = {step.id: StepResult(id=step.id) for step in self.config.steps}

        success = True

        self.logger.info(
            "Starting pipeline '%s'",
            self.config.pipeline.name,
        )

        for step_id in self.graph.order:
            config = self.step_configs[step_id]
            result = step_results[step_id]

            resolved_inputs = {
                parameter_name: context.artifacts[upstream_step].value
                for parameter_name, upstream_step in config.inputs.items()
            }

            result.status = StepStatus.RUNNING

            self.logger.info(
                "Running step '%s'",
                step_id,
            )

            step_start = perf_counter()

            try:
                step_class = get_step(config.type)

                step = step_class(config)

                value = step.execute(
                    context=context,
                    inputs=resolved_inputs,
                )

                result.duration = perf_counter() - step_start

                result.status = StepStatus.SUCCESS

                context.artifacts[step_id] = Artifact(
                    name=step_id,
                    value=value,
                    metadata={
                        "step_type": config.type,
                        "duration": result.duration,
                    },
                )

                self.logger.info(
                    "Completed step '%s' in %.3fs",
                    step_id,
                    result.duration,
                )

            except Exception as exc:
                result.duration = perf_counter() - step_start

                result.status = StepStatus.FAILED
                result.error = str(exc)

                success = False

                self.logger.exception(
                    "Step '%s' failed",
                    step_id,
                )

                break

        # Steps that never ran because an earlier step failed.
        for result in step_results.values():
            if result.status == StepStatus.PENDING:
                result.status = StepStatus.SKIPPED

        pipeline_duration = perf_counter() - pipeline_start

        if success:
            self.logger.info(
                "Pipeline '%s' completed in %.3fs",
                self.config.pipeline.name,
                pipeline_duration,
            )
        else:
            self.logger.error(
                "Pipeline '%s' failed after %.3fs",
                self.config.pipeline.name,
                pipeline_duration,
            )

        return PipelineResult(
            name=self.config.pipeline.name,
            success=success,
            duration=pipeline_duration,
            steps=step_results,
            artifacts=context.artifacts,
        )
