from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Artifact:
    name: str
    value: Any
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class StepResult:
    id: str
    status: StepStatus = StepStatus.PENDING
    duration: float = 0.0
    error: str | None = None


@dataclass
class PipelineResult:
    name: str
    success: bool
    duration: float
    steps: dict[str, StepResult]
    artifacts: dict[str, Artifact]

    def artifact(self, name: str) -> Any:
        return self.artifacts[name].value


@dataclass
class ExecutionContext:
    run_id: str
    logger: logging.Logger
    artifacts: dict[str, Artifact] = field(
        default_factory=dict
    )