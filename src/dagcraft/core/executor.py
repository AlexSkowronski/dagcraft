from __future__ import annotations

import logging
import uuid
from time import perf_counter

from dagcraft.core.compiler import CompiledPipeline
from dagcraft.core.runtime import (
    Artifact,
    ExecutionContext,
    PipelineResult,
    StepResult,
    StepStatus,
)


class Executor:
    """Runs a compiled pipeline's steps in graph order.

    A step is skipped when a step it depends on didn't succeed; other steps
    still run. With ``fail_fast``, every step after the first failure is
    skipped instead.
    """

    def __init__(
        self,
        pipeline: CompiledPipeline,
        logger: logging.Logger | None = None,
        fail_fast: bool = False,
    ):
        self.pipeline = pipeline
        self.logger = logger or logging.getLogger("dagcraft")
        self.fail_fast = fail_fast

    def run(self) -> PipelineResult:
        pipeline_start = perf_counter()

        context = ExecutionContext(
            run_id=str(uuid.uuid4()),
            logger=self.logger,
            params=self.pipeline.params,
            connections=self.pipeline.connections,
        )

        step_results = {
            step_id: StepResult(id=step_id) for step_id in self.pipeline.steps
        }

        success = True

        self.logger.info(
            "Starting pipeline '%s'",
            self.pipeline.name,
        )

        stopped = False

        try:
            for step_id in self.pipeline.graph.order:
                result = step_results[step_id]
                blocker = self._unsuccessful_upstream(step_id, step_results)

                if stopped:
                    self._skip(result, "an earlier step failed and fail_fast is on")
                elif blocker is not None:
                    self._skip(result, f"upstream step '{blocker}' did not succeed")
                elif not self._run_step(step_id, context, result):
                    success = False
                    stopped = self.fail_fast
        finally:
            context.close_connections()

        pipeline_duration = perf_counter() - pipeline_start

        if success:
            self.logger.info(
                "Pipeline '%s' completed in %.3fs",
                self.pipeline.name,
                pipeline_duration,
            )
        else:
            self.logger.error(
                "Pipeline '%s' failed after %.3fs",
                self.pipeline.name,
                pipeline_duration,
            )

        return PipelineResult(
            name=self.pipeline.name,
            success=success,
            duration=pipeline_duration,
            steps=step_results,
            artifacts=context.artifacts,
        )

    def _unsuccessful_upstream(
        self,
        step_id: str,
        step_results: dict[str, StepResult],
    ) -> str | None:
        """Return the first step this one depends on that didn't succeed."""
        dependencies = self.pipeline.graph.dependencies[step_id]

        for upstream in self.pipeline.graph.order:
            if (
                upstream in dependencies
                and step_results[upstream].status != StepStatus.SUCCESS
            ):
                return upstream
        return None

    def _skip(self, result: StepResult, reason: str) -> None:
        result.status = StepStatus.SKIPPED

        self.logger.warning(
            "Skipping step '%s': %s",
            result.id,
            reason,
        )

    def _run_step(
        self,
        step_id: str,
        context: ExecutionContext,
        result: StepResult,
    ) -> bool:
        step = self.pipeline.steps[step_id]

        resolved_inputs = {
            parameter_name: context.artifacts[upstream_step].value
            for parameter_name, upstream_step in step.config.inputs.items()
        }

        result.status = StepStatus.RUNNING

        self.logger.info(
            "Running step '%s'",
            step_id,
        )

        step_start = perf_counter()

        try:
            value = step.execute(
                context=context,
                inputs=resolved_inputs,
            )
        except Exception as exc:
            result.duration = perf_counter() - step_start
            result.status = StepStatus.FAILED
            result.error = str(exc)
            result.exception = exc

            self.logger.exception(
                "Step '%s' failed",
                step_id,
            )

            return False

        result.duration = perf_counter() - step_start
        result.status = StepStatus.SUCCESS

        context.artifacts[step_id] = Artifact(
            name=step_id,
            value=value,
            metadata={
                "step_type": step.config.type,
                "duration": result.duration,
            },
        )

        self.logger.info(
            "Completed step '%s' in %.3fs",
            step_id,
            result.duration,
        )

        return True
