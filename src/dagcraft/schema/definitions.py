"""
Building blocks shared by the schemas: models, types and descriptions.
"""

import inspect
from typing import Any

from pydantic import BaseModel, TypeAdapter


class Definitions:
    """
    Turns pydantic models into schemas, collecting the ``$defs`` they share.
    """

    def __init__(self) -> None:
        self.defs: dict[str, Any] = {}

    def model(self, model: type[BaseModel]) -> dict[str, Any]:
        """
        ``model``'s schema, with its nested models moved to the shared ``$defs``.
        """
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        self.defs.update(schema.pop("$defs", {}))
        return schema


def type_schema(annotation: Any) -> dict[str, Any]:
    """
    The schema for a Python type annotation; any value if it has none.
    """
    if annotation is Any or annotation is inspect.Parameter.empty:
        return {}

    try:
        return TypeAdapter(annotation).json_schema()
    except Exception:  # noqa: BLE001 - types JSON can't describe allow anything
        return {}


def described(schema: dict[str, Any], thing: object) -> dict[str, Any]:
    """
    ``schema`` with ``thing``'s docstring as its description.

    Editors show ``markdownDescription`` where they can, so code there is in
    single backticks.
    """
    doc = inspect.getdoc(thing)

    if not doc:
        return schema

    return {
        **schema,
        "description": doc.replace("``", ""),
        "markdownDescription": doc.replace("``", "`"),
    }


def by_type(schemas: dict[str, dict[str, Any]], what: str) -> dict[str, Any]:
    """
    An object whose ``type`` picks which of ``schemas`` it must match.

    ``what`` names the things being typed, such as "step", for the ``type``
    field's description.
    """
    return {
        "type": "object",
        "required": ["type"],
        "properties": {
            "type": {"enum": sorted(schemas), "description": f"The {what}'s type."}
        },
        "allOf": [
            {
                "if": {"properties": {"type": {"const": name}}, "required": ["type"]},
                "then": schema,
            }
            for name, schema in schemas.items()
        ],
    }
