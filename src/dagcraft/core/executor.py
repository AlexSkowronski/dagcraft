from __future__ import annotations

import heapq
import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from time import perf_counter
from typing import Any

from dagcraft.core.compiler import CompiledPipeline
from dagcraft.core.runtime import (
    Artifact,
    ExecutionContext,
    PipelineResult,
    RunLogger,
    StepResult,
    StepStatus,
)


class InlineExecutor:
    """Runs each submitted call straight away, in the calling thread."""

    def submit(self, function: Callable[..., Any], *args: Any) -> Future[Any]:
        future: Future[Any] = Future()
        future.set_result(function(*args))
        return future

    def __enter__(self) -> InlineExecutor:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class Executor:
    """Runs a compiled pipeline's steps in graph order.

    Up to ``max_workers`` steps run at once, each starting once its inputs
    are ready, earliest declared first. A step is skipped when a step it
    depends on didn't succeed; other steps still run. With ``fail_fast``,
    every step not yet started after the first failure is skipped instead.
    """

    def __init__(
        self,
        pipeline: CompiledPipeline,
        *,
        logger: logging.Logger | None = None,
        fail_fast: bool = False,
        run_id: str | None = None,
        keep_artifacts: bool = True,
        max_workers: int = 1,
    ):
        self.pipeline = pipeline
        self.fail_fast = fail_fast
        self.keep_artifacts = keep_artifacts
        self.max_workers = max_workers
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.logger = RunLogger(
            logger or logging.getLogger("dagcraft"),
            {"pipeline": pipeline.name, "run_id": self.run_id},
        )

    def run(self) -> PipelineResult:
        pipeline_start = perf_counter()

        context = ExecutionContext(
            run_id=self.run_id,
            logger=self.logger,
            params=self.pipeline.params,
            connections=self.pipeline.connections,
        )

        step_results = {
            step_id: StepResult(id=step_id) for step_id in self.pipeline.steps
        }

        self.logger.info("Starting run")

        try:
            success = self._run_steps(context, step_results)
        finally:
            context.close_connections()

        pipeline_duration = perf_counter() - pipeline_start

        if success:
            self.logger.info("Run completed in %.3fs", pipeline_duration)
        else:
            self.logger.error("Run failed after %.3fs", pipeline_duration)

        return PipelineResult(
            name=self.pipeline.name,
            run_id=self.run_id,
            success=success,
            duration=pipeline_duration,
            steps=step_results,
            artifacts=context.artifacts,
        )

    def _run_steps(
        self,
        context: ExecutionContext,
        step_results: dict[str, StepResult],
    ) -> bool:
        """Run, or skip, every step. Returns whether all of them succeeded."""
        graph = self.pipeline.graph
        position = {step_id: index for index, step_id in enumerate(graph.order)}
        dependents: dict[str, list[str]] = {step_id: [] for step_id in graph.order}
        waiting = {step_id: len(graph.dependencies[step_id]) for step_id in graph.order}

        for step_id in graph.order:
            for upstream in graph.dependencies[step_id]:
                dependents[upstream].append(step_id)

        ready = [
            (position[step_id], step_id)
            for step_id in graph.order
            if not waiting[step_id]
        ]
        running: dict[Future[bool], str] = {}
        consumers = self._count_consumers()
        success = True
        stopped = False

        def finish(step_id: str) -> None:
            self._release_outputs(step_id, consumers, context)

            for dependent in dependents[step_id]:
                waiting[dependent] -= 1

                if not waiting[dependent]:
                    heapq.heappush(ready, (position[dependent], dependent))

        pool = (
            ThreadPoolExecutor(self.max_workers, thread_name_prefix="dagcraft")
            if self.max_workers > 1
            else InlineExecutor()
        )

        with pool:
            while ready or running:
                # Start (or skip) ready steps, earliest declared first.
                while ready and len(running) < self.max_workers:
                    _, step_id = heapq.heappop(ready)
                    result = step_results[step_id]
                    blocker = self._unsuccessful_upstream(step_id, step_results)

                    if stopped:
                        self._skip(result, "an earlier step failed and fail_fast is on")
                        finish(step_id)
                    elif blocker is not None:
                        self._skip(result, f"upstream step '{blocker}' did not succeed")
                        finish(step_id)
                    else:
                        future = pool.submit(self._run_step, step_id, context, result)
                        running[future] = step_id

                if not running:
                    continue

                done, _ = wait(running, return_when=FIRST_COMPLETED)

                for future in sorted(
                    done, key=lambda future: position[running[future]]
                ):
                    step_id = running.pop(future)

                    if not future.result():
                        success = False
                        stopped = stopped or self.fail_fast

                    finish(step_id)

        return success

    def _count_consumers(self) -> dict[str, int]:
        """How many steps take each step's output as an input."""
        consumers = dict.fromkeys(self.pipeline.graph.order, 0)

        for dependencies in self.pipeline.graph.dependencies.values():
            for upstream in dependencies:
                consumers[upstream] += 1

        return consumers

    def _release_outputs(
        self,
        step_id: str,
        consumers: dict[str, int],
        context: ExecutionContext,
    ) -> None:
        """Without keep_artifacts, drop outputs no remaining step needs."""
        if self.keep_artifacts:
            return

        for upstream in self.pipeline.graph.dependencies[step_id]:
            consumers[upstream] -= 1

            if consumers[upstream] == 0:
                context.artifacts.pop(upstream, None)

        if consumers[step_id] == 0:
            context.artifacts.pop(step_id, None)

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
        attempts = step.config.retries + 1

        for attempt in range(1, attempts + 1):
            result.attempts = attempt

            try:
                value = step.execute(
                    context=context,
                    inputs=resolved_inputs,
                )
            except Exception as exc:
                if attempt < attempts:
                    delay = step.config.retry_delay * 2 ** (attempt - 1)
                    self.logger.warning(
                        "Step '%s' failed (attempt %d of %d), retrying in %.1fs: %s",
                        step_id,
                        attempt,
                        attempts,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                    continue

                result.duration = perf_counter() - step_start
                result.status = StepStatus.FAILED
                result.error = str(exc)
                result.exception = exc

                self.logger.exception(
                    "Step '%s' failed%s",
                    step_id,
                    f" after {attempts} attempts" if attempts > 1 else "",
                )

                return False

            break

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
