import pytest

from dagcraft.exceptions import RegistryError
from dagcraft.registry import ConnectionTypeRegistry, Registry


class Base:
    pass


class Middle(Base):
    pass


class Leaf(Middle):
    pass


def test_registry_rejects_duplicate_names():
    registry = Registry("widget")
    registry.register("a")(object)

    with pytest.raises(RegistryError, match="A widget named 'a' is already"):
        registry.register("a")(object)


def test_unknown_name_lists_the_available_ones():
    registry = Registry("widget")
    registry.register("b")(object)
    registry.register("a")(object)

    with pytest.raises(RegistryError, match=r"Unknown widget: 'c'\. Available: a, b\."):
        registry.get("c")


def test_nearest_registered_base_class_wins():
    registry = ConnectionTypeRegistry("reader")
    registry.register(Base)("for base")
    registry.register(Middle)("for middle")

    assert registry.find(Leaf()) == "for middle"
    assert registry.find(Base()) == "for base"
    assert registry.find(object()) is None


def test_connection_type_registered_once():
    registry = ConnectionTypeRegistry("reader")
    registry.register(Base)("first")

    with pytest.raises(RegistryError, match="A reader for Base is already"):
        registry.register(Base)("second")
