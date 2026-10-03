"""
What an operation is, and registering your own.
"""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dagcraft.registry import OPERATIONS


@dataclass(frozen=True)
class Operation:
    """
    A named function a transform applies: ``function(data, **options)``.

    ``main`` is the option a single value fills, so ``filter: amount > 100``
    means ``filter: {expression: amount > 100}``. ``tables`` are options that
    name another of the step's inputs, such as a join's ``right``; the input's
    data is passed in their place. ``prepare`` turns options into what the
    function takes when the pipeline loads, such as importing a function.
    """

    name: str
    function: Callable[..., Any]
    main: str | None = None
    tables: tuple[str, ...] = ()
    prepare: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def options_from(self, value: Any) -> dict[str, Any]:
        """
        The options an entry gives: a mapping as it is, anything else as ``main``.
        """
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if self.main is None:
            raise ValueError(
                f"takes options as a mapping, such as {self.name}: {{option: value}}."
            )
        return {self.main: value}

    def check(self, options: dict[str, Any], inputs: set[str]) -> dict[str, Any]:
        """
        Check ``options`` against the function and the step's ``inputs``.

        Returns the options ready to apply. Raises ``ValueError`` naming
        unknown or missing options, or inputs the step doesn't have.
        """
        parameters = list(inspect.signature(self.function).parameters.values())[1:]
        names = [p.name for p in parameters if p.kind is not p.VAR_KEYWORD]
        takes_any = any(p.kind is p.VAR_KEYWORD for p in parameters)

        unknown = [name for name in options if name not in names]
        if unknown and not takes_any:
            raise ValueError(
                f"unknown option {', '.join(map(repr, unknown))}; "
                f"it takes {', '.join(names) or 'none'}."
            )

        missing = [
            p.name
            for p in parameters
            if p.default is p.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
            and p.name not in options
        ]
        if missing:
            raise ValueError(f"needs {', '.join(map(repr, missing))}.")

        for table in self.tables:
            name = options.get(table)
            if name is not None and name not in inputs:
                raise ValueError(
                    f"{table}: '{name}' isn't one of this step's inputs "
                    f"({', '.join(sorted(inputs))})."
                )

        return self.prepare(options) if self.prepare else options

    def apply(self, data: Any, options: dict[str, Any], inputs: dict[str, Any]) -> Any:
        """
        Run the function on ``data``, with named inputs swapped for their data.
        """
        tables = {
            table: inputs[options[table]] for table in self.tables if table in options
        }
        return self.function(data, **{**options, **tables})


def register_operation(
    name: str,
    *,
    main: str | None = None,
    tables: tuple[str, ...] = (),
    prepare: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
):
    """
    Decorator that registers ``function(data, **options)`` as an operation.

    See ``Operation`` for ``main``, ``tables`` and ``prepare``. The function
    is returned unchanged, so it can still be called and tested directly.
    """

    def decorator(function):
        OPERATIONS.register(name)(Operation(name, function, main, tables, prepare))
        return function

    return decorator
