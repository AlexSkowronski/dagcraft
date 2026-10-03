"""
The schema for a transform's ``operations``, from each operation's function.
"""

import inspect
import typing
from typing import Any

from dagcraft.operations.base import Operation
from dagcraft.registry import OPERATIONS
from dagcraft.schema.definitions import described, type_schema

INPUT_NAME = {"type": "string", "description": "The name of one of the step's inputs."}


def operations_schema() -> dict[str, Any]:
    """
    A list of operations, each ``name``, ``name: value`` or ``name: {options}``.
    """
    operations = dict(OPERATIONS.items())
    bare = [name for name, operation in operations.items() if not required(operation)]

    return {
        "type": "array",
        "minItems": 1,
        "description": "The operations, applied in order, each to the last result.",
        "items": {
            "anyOf": [
                {"type": "string", "enum": bare},
                {
                    "type": "object",
                    "minProperties": 1,
                    "maxProperties": 1,
                    "additionalProperties": False,
                    "properties": {
                        name: value_schema(operation)
                        for name, operation in operations.items()
                    },
                },
            ]
        },
    }


def value_schema(operation: Operation) -> dict[str, Any]:
    """
    What can follow an operation's name: its options, or its main option.
    """
    options = options_schema(operation)
    choices = [options]

    if operation.main is not None:
        choices.insert(0, options["properties"][operation.main])
    if not required(operation):
        choices.append({"type": "null"})

    return described({"anyOf": choices}, operation.function)


def options_schema(operation: Operation) -> dict[str, Any]:
    """
    An operation's options, from its function's parameters after the data.
    """
    hints = typing.get_type_hints(operation.function)
    properties: dict[str, Any] = {}
    extra: dict[str, Any] | bool = False

    for parameter in parameters(operation):
        hint = hints.get(parameter.name, Any)

        if parameter.kind is parameter.VAR_KEYWORD:
            extra = type_schema(hint)
        elif parameter.name in operation.tables:
            properties[parameter.name] = INPUT_NAME
        else:
            properties[parameter.name] = type_schema(hint)

    if operation.source is not None:
        properties[operation.source] = INPUT_NAME

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": extra,
    }

    if required(operation):
        schema["required"] = required(operation)
    return schema


def parameters(operation: Operation) -> list[inspect.Parameter]:
    """
    The function's parameters after the data it works on.
    """
    return list(inspect.signature(operation.function).parameters.values())[1:]


def required(operation: Operation) -> list[str]:
    """
    The options an operation can't do without.
    """
    return [
        p.name
        for p in parameters(operation)
        if p.default is p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    ]
