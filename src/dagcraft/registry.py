from __future__ import annotations

from typing import Any

from dagcraft.exceptions import RegistryError


class Registry:
    """Named components of one kind, such as step types or formats."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, Any] = {}

    def register(self, name: str):
        """Decorator that registers a class or function under ``name``."""

        def decorator(item):
            if name in self._items:
                raise RegistryError(
                    f"A {self.kind} named '{name}' is already registered."
                )
            self._items[name] = item
            return item

        return decorator

    def get(self, name: str) -> Any:
        try:
            return self._items[name]
        except KeyError:
            available = ", ".join(self.names()) or "none"
            raise RegistryError(
                f"Unknown {self.kind}: '{name}'. Available: {available}."
            ) from None

    def names(self) -> list[str]:
        return sorted(self._items)

    def values(self) -> list[Any]:
        return list(self._items.values())

    def __contains__(self, name: object) -> bool:
        return name in self._items


STEPS = Registry("step type")
OPERATIONS = Registry("operation")
CONNECTIONS = Registry("connection type")
FORMATS = Registry("format")

register_step = STEPS.register
register_operation = OPERATIONS.register
register_connection = CONNECTIONS.register
register_format = FORMATS.register
