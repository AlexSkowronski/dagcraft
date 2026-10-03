"""Paths inside file connections, which may use wildcards to match many files."""

WILDCARDS = "*?["


def has_wildcards(path: str) -> bool:
    """Whether ``path`` is a pattern (``*``, ``?``, ``[...]``) rather than one file."""
    return any(character in path for character in WILDCARDS)
