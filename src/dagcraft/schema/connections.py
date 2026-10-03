"""
The schema for the ``connections`` section, from each connection type's model.
"""

from typing import Any

from dagcraft.registry import CONNECTIONS
from dagcraft.schema.definitions import Definitions, by_type, described


def connections_section(defs: Definitions) -> dict[str, Any]:
    """
    Named connections, each matching the model of its ``type``.
    """
    schemas = {}

    for name, connection_class in CONNECTIONS.items():
        schema = defs.model(connection_class.config_model)
        schema.setdefault("properties", {})["type"] = {"const": name}
        schemas[name] = described(schema, connection_class)

    return {
        "type": "object",
        "description": "Named connections: where data lives and how to sign in.",
        "additionalProperties": by_type(schemas, "connection"),
    }
