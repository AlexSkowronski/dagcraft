"""
Running a compiled pipeline from start to finish.
"""

import uuid
from concurrent.futures import FIRST_COMPLETED, Future, wait
from concurrent.futures import Executor as WorkerPool

from dagcraft.core.compiler import CompiledPipeline
from dagcraft.core.connection_manager import ConnectionManager
from dagcraft.core.context import ExecutionContext
from dagcraft.core.outputs import OutputStore
from dagcraft.core.results import PipelineResult, StepResult, StepStatus
from dagcraft.core.scheduler import Scheduler
from dagcraft.core.step_runner import StepRunner
from dagcraft.core.workers import submit_in_context, worker_pool
from dagcraft.logs import get_logger, run_context, step_context
from dagcraft.timing import Timer

logger = get_logger(__name__)


class Executor:
    """
    Runs a compiled pipeline's steps, up to ``max_workers`` at a time.

    The scheduler decides what is ready, the step runner runs each step, and
    the executor connects them: it starts ready steps, waits for running ones
    and records how each ended. Connections opened during the run are closed
    at the end, whatever happens.
    """

    def __init__(
        self,
        pipeline: CompiledPipeline,
        *,
        fail_fast: bool = False,
        run_id: str | None = None,
        keep_outputs: bool = True,
        max_workers: int = 1,
    ) -> None:
        self.pipeline = pipeline
        self.fail_fast = fail_fast
        self.keep_outputs = keep_outputs
        self.max_workers = max_workers
        self.run_id = run_id or uuid.uuid4().hex[:8]

    def run(self) -> PipelineResult:
        """
        Run every step, or skip it, and report the outcome.
        """
        results = {
            step_id: StepResult(
                id=step_id,
            )
            for step_id in self.pipeline.steps
        }
        context = ExecutionContext(
            run_id=self.run_id,
            params=self.pipeline.params,
            connections=ConnectionManager(
                self.pipeline.connections,
            ),
            outputs=OutputStore(
                self.pipeline.graph,
                keep=self.keep_outputs,
            ),
        )

        with (
            run_context(
                self.pipeline.name,
                self.run_id,
            ),
            Timer() as timer,
        ):
            steps = f"{len(results)} step{'' if len(results) == 1 else 's'}"
            at_once = (
                f", up to {self.max_workers} at once" if self.max_workers > 1 else ""
            )
            logger.info("Starting run: %s%s", steps, at_once)

            try:
                self._run_steps(context, results)
            finally:
                context.connections.close_all()

            success = not any(r.status == StepStatus.FAILED for r in results.values())

            if success:
                logger.info("Run succeeded in %.3fs", timer.elapsed)
            else:
                logger.error("Run failed after %.3fs", timer.elapsed)

        return PipelineResult(
            name=self.pipeline.name,
            run_id=self.run_id,
            success=success,
            duration=timer.elapsed,
            steps=results,
            outputs=context.outputs.as_dict(),
        )

    def _run_steps(
        self,
        context: ExecutionContext,
        results: dict[str, StepResult],
    ) -> None:
        scheduler = Scheduler(self.pipeline.graph, fail_fast=self.fail_fast)
        runner = StepRunner(self.pipeline.steps, context)
        running: dict[Future[None], str] = {}

        with worker_pool(self.max_workers) as pool:
            while scheduler.has_ready() or running:
                self._start_ready(scheduler, pool, runner, running, results)

                for step_id in self._wait_for_any(running, scheduler):
                    self._finish(step_id, results[step_id], scheduler, context)

    def _start_ready(
        self,
        scheduler: Scheduler,
        pool: WorkerPool,
        runner: StepRunner,
        running: dict[Future[None], str],
        results: dict[str, StepResult],
    ) -> None:
        """
        Start or skip ready steps, earliest declared first, while there's room.
        """
        while scheduler.has_ready() and len(running) < self.max_workers:
            step_id = scheduler.pop_ready()
            reason = scheduler.skip_reason(step_id)

            if reason is None:
                running[submit_in_context(pool, runner.run, results[step_id])] = step_id
                continue

            results[step_id].status = StepStatus.SKIPPED

            with step_context(step_id):
                logger.warning("skipped: %s", reason)

            self._finish(step_id, results[step_id], scheduler, runner.context)

    def _wait_for_any(
        self,
        running: dict[Future[None], str],
        scheduler: Scheduler,
    ) -> list[str]:
        """
        Wait for at least one running step; return those done, in run order.
        """
        if not running:
            return []

        done, _ = wait(running, return_when=FIRST_COMPLETED)

        for future in done:
            future.result()  # re-raise anything that escaped the step runner

        finished = [running.pop(future) for future in done]
        return sorted(finished, key=scheduler.position)

    def _finish(
        self,
        step_id: str,
        result: StepResult,
        scheduler: Scheduler,
        context: ExecutionContext,
    ) -> None:
        scheduler.finished(step_id, result.status)
        context.outputs.step_finished(step_id)
