"""
The JSON Schemas for pipeline files and shared connection files.
"""

import json
from pathlib import Path
from typing import Any

# Importing these packages registers the built-in components.
from dagcraft import connections as _connections  # noqa: F401
from dagcraft import operations as _operations  # noqa: F401
from dagcraft import readers as _readers  # noqa: F401
from dagcraft import steps as _steps  # noqa: F401
from dagcraft import writers as _writers  # noqa: F401
from dagcraft.config.pipeline import PipelineMeta
from dagcraft.schema.connections import connections_section
from dagcraft.schema.definitions import Definitions
from dagcraft.schema.steps import steps_section

DRAFT = "http://json-schema.org/draft-07/schema#"
PUBLISHED = "https://alexskowronski.github.io/dagcraft/schemas/"

# ${params.NAME} and ${env:NAME} can stand for any value, so wherever a
# number, boolean or list is expected, a reference is allowed too.
REFERENCE = {
    "type": "string",
    "pattern": r"^\$\{[^}]+\}$",
    "description": "A ${params.NAME} or ${env:NAME} reference.",
}
REFERABLE = {"integer", "number", "boolean", "array"}


def pipeline_schema() -> dict[str, Any]:
    """
    The schema for pipeline files.
    """
    defs = Definitions()
    schema = {
        "$schema": DRAFT,
        "$id": f"{PUBLISHED}pipeline.json",
        "title": "dagcraft pipeline",
        "type": "object",
        "required": ["pipeline", "steps"],
        "additionalProperties": False,
        "properties": {
            "pipeline": defs.model(PipelineMeta),
            "include": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Files of shared connections, relative to the folder you run from."
                ),
            },
            "params": {
                "type": "object",
                "description": "Named values, used elsewhere as ${params.NAME}.",
            },
            "connections": connections_section(defs),
            "steps": steps_section(defs),
        },
    }
    return finish(schema, defs)


def connections_schema() -> dict[str, Any]:
    """
    The schema for files of shared connections, which pipelines ``include``.
    """
    defs = Definitions()
    schema = {
        "$schema": DRAFT,
        "$id": f"{PUBLISHED}connections.json",
        "title": "dagcraft shared connections",
        "type": "object",
        "required": ["connections"],
        "additionalProperties": False,
        "properties": {"connections": connections_section(defs)},
    }
    return finish(schema, defs)


def write_schemas(folder: Path) -> list[Path]:
    """
    Write ``pipeline.json`` and ``connections.json`` to ``folder``.
    """
    folder.mkdir(parents=True, exist_ok=True)
    written = []

    for name, schema in [
        ("pipeline.json", pipeline_schema()),
        ("connections.json", connections_schema()),
    ]:
        path = folder / name
        text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)

    return written


def finish(schema: dict[str, Any], defs: Definitions) -> dict[str, Any]:
    """
    Add the shared ``$defs``, and allow references wherever values are typed.
    """
    return allow_references({**schema, "$defs": defs.defs})


def allow_references(node: Any) -> Any:
    """
    ``node`` with every number, boolean and list also accepting a reference.
    """
    if isinstance(node, list):
        return [allow_references(item) for item in node]

    if not isinstance(node, dict):
        return node

    node = {key: allow_references(value) for key, value in node.items()}
    kind = node.get("type")

    # In a "properties" map, "type" is a field's schema, not a type name.
    # Lists of objects (steps, operations) are structure, not values, and
    # wrapping them would make editors report errors on the whole list.
    if (
        isinstance(kind, str)
        and kind in REFERABLE
        and not (kind == "array" and holds_objects(node.get("items", {})))
    ):
        return {"anyOf": [node, REFERENCE]}
    return node


def holds_objects(schema: dict[str, Any]) -> bool:
    """
    Whether ``schema`` describes objects, or a choice that includes them.
    """
    if schema.get("type") == "object" or "properties" in schema or "allOf" in schema:
        return True
    return any(holds_objects(choice) for choice in schema.get("anyOf", []))
