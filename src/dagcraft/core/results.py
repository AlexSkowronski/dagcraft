"""
What running, planning or checking a pipeline reports back.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    """
    Where a step got to in a run.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class StepResult:
    """
    The outcome of one step: its status, timing, attempts and any error.
    """

    id: str
    status: StepStatus = StepStatus.PENDING
    duration: float = 0.0
    attempts: int = 0
    error: str | None = None
    exception: BaseException | None = field(default=None, repr=False)


@dataclass
class PipelineResult:
    """
    The outcome of a run.

    ``outputs`` maps step ids to what each step returned, usually a
    DataFrame. It's empty for a run with ``keep_outputs=False``.
    """

    name: str
    run_id: str
    success: bool
    duration: float
    steps: dict[str, StepResult]
    outputs: dict[str, Any]

    def output(self, step_id: str) -> Any:
        """
        What step ``step_id`` returned; raises ``KeyError`` saying why if absent.
        """
        try:
            return self.outputs[step_id]
        except KeyError:
            raise KeyError(
                f"No output for step '{step_id}': it didn't succeed, or the run "
                "was made with keep_outputs=False."
            ) from None

    @property
    def failed_steps(self) -> list[StepResult]:
        """
        Every step that failed, in declared order.
        """
        return [
            step for step in self.steps.values() if step.status == StepStatus.FAILED
        ]

    @property
    def failed_step(self) -> StepResult | None:
        """
        The first step that failed, if any.
        """
        failed = self.failed_steps
        return failed[0] if failed else None


@dataclass(frozen=True)
class PlannedStep:
    """
    A step as it would run: see ``Pipeline.plan``.
    """

    id: str
    description: str
    inputs: dict[str, str]


@dataclass(frozen=True)
class ConnectionCheck:
    """
    The outcome of checking one connection: see ``Pipeline.check_connections``.
    """

    name: str
    type: str
    ok: bool
    message: str
