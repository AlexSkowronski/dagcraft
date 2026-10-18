"""
Helpers for steps that use a connection: finding it, and its reader or writer.
"""

from typing import Any

from dagcraft.connections import Connection
from dagcraft.registry import ConnectionTypeRegistry
from dagcraft.templates import Templates


def find_connection(connections: dict[str, Connection], name: str) -> Connection:
    """
    The connection called ``name``; raises ``ValueError`` listing the others.
    """
    try:
        return connections[name]
    except KeyError:
        available = ", ".join(sorted(connections))
        raise ValueError(
            f"Unknown connection '{name}'. Available: {available}."
        ) from None


def prepare_handler(
    registry: ConnectionTypeRegistry,
    connection: Connection,
    fields: dict[str, Any],
    templates: Templates,
    action: str,
) -> Any:
    """
    The reader or writer for ``connection``, set up from a step's fields.

    Finds the class registered for the connection's type, renders the
    fields it says are templates, validates them with its options model and
    prepares it. ``action`` ("reading" or "writing") is for the error when
    the connection supports neither.
    """
    handler_class = registry.find(connection)

    if handler_class is None:
        raise ValueError(f"Connection '{connection.name}' does not support {action}.")

    rendered = {
        name: render_field(templates, name, value, handler_class.template_fields)
        for name, value in fields.items()
    }
    handler = handler_class(handler_class.options_model.model_validate(rendered))
    handler.prepare(connection, templates)
    return handler


def render_field(
    templates: Templates,
    name: str,
    value: Any,
    template_fields: tuple[str, ...],
) -> Any:
    """
    ``value`` rendered if field ``name`` is one of the ``template_fields``.
    """
    if name in template_fields and isinstance(value, str):
        return templates.render(value, name)
    return value
