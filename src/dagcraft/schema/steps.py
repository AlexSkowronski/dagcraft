"""
The schema for the ``steps`` section, from each step type's model.
"""

from typing import Any

from dagcraft.registry import (
    CONNECTIONS,
    READERS,
    STEPS,
    WRITERS,
    ConnectionTypeRegistry,
)
from dagcraft.schema.definitions import Definitions, by_type, described
from dagcraft.schema.operations import operations_schema

# Steps whose other fields come from the reader or writer of their connection.
HANDLERS = {"read": READERS, "write": WRITERS}


def steps_section(defs: Definitions) -> dict[str, Any]:
    """
    The list of steps, each matching the model of its ``type``.
    """
    schemas = {}

    for name, step_class in STEPS.items():
        schema = defs.model(step_class.config_model)
        properties = schema.setdefault("properties", {})
        properties["type"] = {"const": name}

        if name in HANDLERS:
            properties.update(handler_fields(defs, HANDLERS[name]))
            schema["additionalProperties"] = False
        if "operations" in properties:
            properties["operations"] = operations_schema()

        schemas[name] = described(schema, step_class)

    return {
        "type": "array",
        "description": "The steps. Each has an id and a type.",
        "items": by_type(schemas, "step"),
    }


def handler_fields(
    defs: Definitions, registry: ConnectionTypeRegistry
) -> dict[str, Any]:
    """
    Every reader's (or writer's) fields, each saying which connections take it.

    The editor can't tell which connection a step uses, so it offers them
    all; loading the pipeline checks they suit the connection.
    """
    fields: dict[str, Any] = {}
    kinds: dict[str, list[str]] = {}

    for connection_type, handler in registry.items():
        names = [
            name
            for name, cls in CONNECTIONS.items()
            if issubclass(cls, connection_type)
        ]

        for field, schema in defs.model(handler.options_model)["properties"].items():
            fields.setdefault(field, schema)
            kinds.setdefault(field, []).extend(names)

    return {
        field: {**schema, "description": f"For {join(kinds[field])} connections."}
        for field, schema in fields.items()
    }


def join(names: list[str]) -> str:
    """
    ``a``, ``a and b``, ``a, b and c``.
    """
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
