"""
Registries of the components a pipeline file can name.

Built-in components register themselves when their package is imported;
your own register the same way, with the ``register_*`` decorators.
"""

from typing import Any

from dagcraft.exceptions import RegistryError


class Registry:
    """
    Named components of one kind, such as step types or formats.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, Any] = {}

    def register(self, name: str):
        """
        Decorator that registers a class or function under ``name``.
        """

        def decorator(item):
            if name in self._items:
                raise RegistryError(
                    f"A {self.kind} named '{name}' is already registered."
                )
            self._items[name] = item
            return item

        return decorator

    def get(self, name: str) -> Any:
        """
        The component called ``name``; raises ``RegistryError`` if unknown.
        """
        try:
            return self._items[name]
        except KeyError:
            available = ", ".join(self.names()) or "none"
            raise RegistryError(
                f"Unknown {self.kind}: '{name}'. Available: {available}."
            ) from None

    def names(self) -> list[str]:
        """
        Every registered name, sorted.
        """
        return sorted(self._items)

    def values(self) -> list[Any]:
        """
        Every registered component, in the order they were registered.
        """
        return list(self._items.values())

    def __contains__(self, name: object) -> bool:
        return name in self._items


class ConnectionTypeRegistry:
    """
    Classes registered for a kind of connection, such as its reader.

    Looking up a connection finds the class registered for its own type, or
    else for the nearest base class: a reader registered for
    ``FileConnection`` serves every file connection.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[type, Any] = {}

    def register(self, connection_type: type):
        """
        Decorator that registers a class for ``connection_type``.
        """

        def decorator(item):
            if connection_type in self._items:
                raise RegistryError(
                    f"A {self.kind} for {connection_type.__name__} is already "
                    "registered."
                )
            self._items[connection_type] = item
            return item

        return decorator

    def find(self, connection: object) -> Any | None:
        """
        The class registered for ``connection``'s type, or ``None``.
        """
        for cls in type(connection).__mro__:
            if cls in self._items:
                return self._items[cls]
        return None


STEPS = Registry("step type")
OPERATIONS = Registry("operation")
CONNECTIONS = Registry("connection type")
FORMATS = Registry("format")
READERS = ConnectionTypeRegistry("reader")
WRITERS = ConnectionTypeRegistry("writer")

register_step = STEPS.register
register_operation = OPERATIONS.register
register_connection = CONNECTIONS.register
register_format = FORMATS.register
register_reader = READERS.register
register_writer = WRITERS.register
