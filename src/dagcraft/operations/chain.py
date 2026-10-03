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
    def source_input(self) -> str | None:
        """
        The input this call works on instead of the result so far, if any.
        """
        return self.operation.source_input(self.options)

    @property
    def table_inputs(self) -> list[str]:
        """
        The inputs this call names: its source and its other tables.
        """
        names = [self.options.get(table) for table in self.operation.tables]
        return [name for name in [self.source_input, *names] if name is not None]

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
    ``name: {option: value, ...}``. The chain starts from the ``data`` input,
    or from the input the first operation names as its source (a join's
    ``left``). Raises ``ValueError`` naming the entry at fault, or an input
    no operation uses.
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

    check_start(calls, inputs)
    check_inputs_used(calls, inputs)
    return calls


def check_start(calls: list[OperationCall], inputs: set[str]) -> None:
    """
    The chain needs somewhere to start, and only its first call can choose.
    """
    for call in calls[1:]:
        if call.source_input is not None:
            raise ValueError(
                f"{call.label}: only the first operation can set "
                f"{call.operation.source}; after that, the left side is the "
                "result so far."
            )

    if calls[0].source_input is None and "data" not in inputs:
        raise ValueError(
            "A transform starts from its 'data' input, or from the table its "
            "first operation names, such as join: {left: orders, right: "
            "customers, on: customer_id}. This one has neither."
        )


def check_inputs_used(calls: list[OperationCall], inputs: set[str]) -> None:
    """
    Every input must be the starting table or named by an operation.
    """
    used = {calls[0].source_input or "data"}

    for call in calls:
        used.update(call.table_inputs)

    unused = sorted(inputs - used)

    if unused:
        raise ValueError(
            f"No operation uses the input {', '.join(map(repr, unused))}: name "
            "it in one, such as join's right, or remove it."
        )


def entry_parts(entry: Any) -> tuple[str, Any]:
    """
    An entry's operation name and value: ``filter: x`` is ``("filter", "x")``.
    """
    if isinstance(entry, str):
        return entry, None
    [(name, value)] = entry.items()
    return name, value


def run_operations(calls: list[OperationCall], inputs: dict[str, Any]) -> Any:
    """
    Apply each call to the result of the one before.

    The chain starts from the ``data`` input, unless the first call names
    its own (a join's ``left``).

    Logs what each did at DEBUG. A failure raises ``ExecutionError`` naming
    the operation, with the original error chained.
    """
    data = inputs.get("data")

    for call in calls:
        before = describe_data(inputs[call.source_input] if call.source_input else data)

        try:
            data = call.operation.apply(data, call.options, inputs)
        except Exception as exc:
            raise ExecutionError(f"{call.label} failed: {exc}") from exc

        logger.debug("%s: %s -> %s", call.operation.name, before, describe_data(data))

    return data
