from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dagcraft.connections import Connection


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Artifact:
    name: str
    value: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    id: str
    status: StepStatus = StepStatus.PENDING
    duration: float = 0.0
    error: str | None = None
    exception: BaseException | None = field(default=None, repr=False)


@dataclass(frozen=True)
class PlannedStep:
    """A step as it would run: see ``Pipeline.plan``."""

    id: str
    description: str
    inputs: dict[str, str]


@dataclass
class PipelineResult:
    name: str
    success: bool
    duration: float
    steps: dict[str, StepResult]
    artifacts: dict[str, Artifact]

    def artifact(self, name: str) -> Any:
        return self.artifacts[name].value

    @property
    def failed_steps(self) -> list[StepResult]:
        return [
            step for step in self.steps.values() if step.status == StepStatus.FAILED
        ]

    @property
    def failed_step(self) -> StepResult | None:
        """The first step that failed, if any."""
        failed = self.failed_steps
        return failed[0] if failed else None


@dataclass
class ExecutionContext:
    run_id: str
    logger: logging.Logger
    params: dict[str, Any] = field(default_factory=dict)
    connections: dict[str, Connection] = field(default_factory=dict)
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    opened: list[Connection] = field(default_factory=list)

    def connection(self, name: str) -> Connection:
        """Return a connection, opening it on first use in this run."""
        connection = self.connections[name]

        if connection not in self.opened:
            connection.open()
            self.opened.append(connection)

        return connection

    def close_connections(self) -> None:
        """Close every connection opened during this run, newest first."""
        while self.opened:
            connection = self.opened.pop()

            try:
                connection.close()
            except Exception:
                self.logger.exception(
                    "Failed to close connection '%s'",
                    connection.name,
                )
