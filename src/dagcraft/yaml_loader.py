"""Loading YAML the way pipeline files and ``.yaml`` data files expect."""

import re
from typing import IO, Any

import yaml

BOOL_TAG = "tag:yaml.org,2002:bool"


class Yaml12Loader(yaml.SafeLoader):
    """SafeLoader where only true/false are booleans, as in YAML 1.2.

    PyYAML follows YAML 1.1, which also reads yes, no, on and off as
    booleans, so ``on: customer_id`` would become ``{True: "customer_id"}``.
    """


Yaml12Loader.yaml_implicit_resolvers = {
    first: [(tag, pattern) for tag, pattern in resolvers if tag != BOOL_TAG]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
Yaml12Loader.add_implicit_resolver(
    BOOL_TAG,
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_yaml(source: str | IO[str]) -> Any:
    """Parse YAML text or a text stream. Raises ``yaml.YAMLError`` if invalid."""
    return yaml.load(source, Loader=Yaml12Loader)  # noqa: S506 - a SafeLoader
