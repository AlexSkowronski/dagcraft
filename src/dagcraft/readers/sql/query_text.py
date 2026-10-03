"""Finding the ``:name`` placeholders in SQL text."""

import re

from dagcraft.config.readers import PARTITION_PLACEHOLDERS


def escape_non_code_colons(query: str) -> str:
    r"""Escape colons in comments, strings and quoted names as ``\:``.

    SQLAlchemy reads ``:name`` as a parameter anywhere in a query, even in
    ``-- comments`` and ``'string literals'``, where the database doesn't
    see a placeholder. Escaping those colons leaves parameters only in code.
    """
    pieces = []
    position = 0
    length = len(query)

    while position < length:
        character = query[position]

        if query.startswith("--", position):
            end = query.find("\n", position)
            end = length if end == -1 else end
        elif query.startswith("/*", position):
            end = query.find("*/", position + 2)
            end = length if end == -1 else end + 2
        elif character in "'\"[":
            end = closing_quote(query, position, "]" if character == "[" else character)
        else:
            pieces.append(character)
            position += 1
            continue

        pieces.append(query[position:end].replace(":", "\\:"))
        position = end

    return "".join(pieces)


def closing_quote(query: str, start: int, quote: str) -> int:
    """Index just past the quote closing the one at ``start``.

    A doubled quote inside (``'it''s'``) is part of the text.
    """
    position = start + 1

    while position < len(query):
        if query[position] == quote:
            if query.startswith(quote * 2, position):
                position += 2
                continue
            return position + 1
        position += 1

    return len(query)


def check_partition_placeholders(query: str) -> None:
    """Raise ``ValueError`` unless ``query`` uses both partition placeholders."""
    code = escape_non_code_colons(query)
    missing = [
        name
        for name in PARTITION_PLACEHOLDERS
        if not re.search(rf"(?<![\\\w:]):{name}\b", code)
    ]

    if missing:
        placeholders = " and ".join(f":{name}" for name in missing)
        raise ValueError(f"A partitioned query must use {placeholders}.")
