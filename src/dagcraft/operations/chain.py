"""
A transform's list of operations: checked when the pipeline loads, applied in order.
"""

from dataclasses import dataclass
from typing import Any

from dagcraft.data import describe_data
from dagcraft.exceptions import ExecutionError, PipelineError
from dagcraft.logs import get_logger
from dagcraft.operations.base import Operation
from dagcraft.registry import OPERATIONS

logger = get_logger(__name__)


@dataclass(frozen=True)
class OperationCall:
    """
    One entry of a transform's operations: what to apply, with which options.
    """

    position: int
    operation: Operation
    options: dict[str, Any]

    @property
    def label(self) -> str:
        """
        How errors name this entry: ``operation 3 (join)``.
        """
        return f"operation {self.position} ({self.operation.name})"


def parse_operations(entries: list[Any], inputs: set[str]) -> list[OperationCall]:
    """
    Turn a transform's ``operations`` into checked calls.

    Each entry is ``name``, ``name: value`` (the operation's main option) or
    ``name: {option: value, ...}``. Raises ``ValueError`` naming the entry at
    fault.
    """
    calls = []

    for position, entry in enumerate(entries, start=1):
        name, value = entry_parts(entry)

        try:
            operation = OPERATIONS.get(name)
            options = operation.check(operation.options_from(value), inputs)
        except (ValueError, PipelineError) as exc:
            raise ValueError(f"operation {position} ({name}): {exc}") from exc

        calls.append(OperationCall(position, operation, options))

    return calls


def entry_parts(entry: Any) -> tuple[str, Any]:
    """
    An entry's operation name and value: ``filter: x`` is ``("filter", "x")``.
    """
    if isinstance(entry, str):
        return entry, None
    [(name, value)] = entry.items()
    return name, value


def run_operations(
    calls: list[OperationCall],
    data: Any,
    inputs: dict[str, Any],
) -> Any:
    """
    Apply each call to the result of the one before, starting from ``data``.

    Logs what each did at DEBUG. A failure raises ``ExecutionError`` naming
    the operation, with the original error chained.
    """
    for call in calls:
        before = describe_data(data)

        try:
            data = call.operation.apply(data, call.options, inputs)
        except Exception as exc:
            raise ExecutionError(f"{call.label} failed: {exc}") from exc

        logger.debug("%s: %s -> %s", call.operation.name, before, describe_data(data))

    return data
