"""
Running one step: its inputs, its retries, and how it ended.
"""

import time
from typing import Any

from dagcraft.core.context import ExecutionContext
from dagcraft.core.results import StepResult, StepStatus
from dagcraft.data import describe_data
from dagcraft.exceptions import NothingFound
from dagcraft.logs import get_logger, step_context
from dagcraft.steps import BaseStep
from dagcraft.timing import Timer

logger = get_logger(__name__)


class StepRunner:
    """
    Runs steps one at a time (call ``run`` from several threads to overlap them).

    A step gets the outputs of the steps it depends on as its inputs. A
    failed step is retried up to ``retries`` times, waiting ``retry_delay``
    seconds before the first retry and twice as long before each one after.
    Logs a line when each step starts and ends, saying what it did.
    """

    def __init__(self, steps: dict[str, BaseStep], context: ExecutionContext) -> None:
        self.steps = steps
        self.context = context

    def run(self, result: StepResult) -> None:
        """
        Run the step ``result`` is for, recording the outcome on ``result``.
        """
        step = self.steps[result.id]

        with step_context(result.id), Timer() as timer:
            result.status = StepStatus.RUNNING
            logger.info("started: %s", step.describe())

            try:
                value = self._execute_with_retries(step, result)
            except NothingFound as signal:
                # Not a failure: the steps that need this output are skipped.
                result.duration = timer.elapsed
                result.status = StepStatus.SUCCESS
                result.found_nothing = str(signal)
                logger.warning("found nothing: %s; skipping what needs it", signal)
                return
            except Exception as exc:
                result.duration = timer.elapsed
                result.status = StepStatus.FAILED
                result.error = str(exc)
                result.exception = exc
                attempts = (
                    f" after {result.attempts} attempts" if result.attempts > 1 else ""
                )
                logger.exception("failed%s", attempts)
                return

            result.duration = timer.elapsed
            result.status = StepStatus.SUCCESS
            self.context.outputs.put(result.id, value)
            logger.info("finished in %.3fs: %s", result.duration, describe_data(value))

    def _execute_with_retries(self, step: BaseStep, result: StepResult) -> Any:
        inputs = self.context.outputs.inputs_for(step.config.inputs)
        attempts = step.config.retries + 1
        result.attempts = 1

        while True:
            try:
                return step.execute(self.context, inputs)
            except NothingFound:
                raise  # trying again won't find anything new
            except Exception as exc:
                if result.attempts == attempts:
                    raise

                delay = step.config.retry_delay * 2 ** (result.attempts - 1)
                logger.warning(
                    "failed (attempt %d of %d), retrying in %.1fs: %s",
                    result.attempts,
                    attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
                result.attempts += 1
