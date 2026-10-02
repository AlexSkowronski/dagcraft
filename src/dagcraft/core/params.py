"""``${params.NAME}`` and ``${env:NAME}`` references in pipeline files.

A string that is exactly one reference is replaced by the referenced value,
keeping its type, so ``${params.limit}`` can be a number or a list. A
reference inside a longer string is inserted as text. ``$${...}`` is a
literal ``${...}``.
"""

from __future__ import annotations

import os
import re
from typing import Any

from dagcraft.exceptions import ConfigError

REFERENCE = re.compile(r"(\$?)\$\{([^}]*)\}")
PARAM_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TEXT_TYPES = (str, int, float)


def resolve_params(
    declared: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Combine the file's params with overrides.

    Params may reference environment variables but not each other.
    Overrides must name a param declared in the file.
    """
    unknown = sorted(set(overrides) - set(declared))

    if unknown:
        raise ConfigError(
            f"Unknown parameter: {', '.join(unknown)}. "
            f"Defined: {', '.join(declared) or 'none'}."
        )

    values: dict[str, Any] = {}

    for name, value in declared.items():
        if not PARAM_NAME.fullmatch(name):
            raise ConfigError(
                f"Parameter name '{name}' should be letters, digits and "
                "underscores, not starting with a digit."
            )

        if name in overrides:
            values[name] = overrides[name]
            continue

        try:
            values[name] = substitute(value, None)
        except ValueError as exc:
            raise ConfigError(f"Parameter '{name}': {exc}") from exc

    return values


def substitute(value: Any, params: dict[str, Any] | None, where: str = "") -> Any:
    """Replace references in every string inside ``value``.

    ``params`` is ``None`` while the params themselves are being resolved,
    where only environment variables may be referenced. Raises
    ``ValueError`` naming the field (``where``) with the bad reference.
    """
    if isinstance(value, str):
        return substitute_text(value, params, where)

    if isinstance(value, dict):
        return {
            key: substitute(item, params, join(where, str(key)))
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            substitute(item, params, f"{where}[{index}]")
            for index, item in enumerate(value)
        ]

    return value


def substitute_text(text: str, params: dict[str, Any] | None, where: str) -> Any:
    whole = REFERENCE.fullmatch(text)

    if whole is not None and not whole.group(1):
        return resolve(whole.group(2), params, where)

    def replace(match: re.Match[str]) -> str:
        if match.group(1):
            return match.group(0)[1:]

        value = resolve(match.group(2), params, where)

        if isinstance(value, bool) or not isinstance(value, TEXT_TYPES):
            # A config error, reported like the others.
            raise ValueError(  # noqa: TRY004
                f"{location(where)}${{{match.group(2)}}} is a "
                f"{type(value).__name__} and can only be used as a whole value, "
                "not inside text."
            )
        return str(value)

    return REFERENCE.sub(replace, text)


def resolve(reference: str, params: dict[str, Any] | None, where: str) -> Any:
    if reference.startswith("env:"):
        name, has_default, default = reference.removeprefix("env:").partition(":-")
        value = os.environ.get(name)

        if value is not None:
            return value
        if has_default:
            return default

        raise ValueError(f"{location(where)}environment variable '{name}' is not set.")

    if reference.startswith("params."):
        if params is None:
            raise ValueError("params can't reference other params.")

        name = reference.removeprefix("params.")

        if name not in params:
            raise ValueError(
                f"{location(where)}unknown parameter '{name}'. "
                f"Defined: {', '.join(params) or 'none'}."
            )
        return params[name]

    raise ValueError(
        f"{location(where)}'${{{reference}}}' isn't a reference dagcraft "
        "understands. Use ${params.NAME} or ${env:NAME}."
    )


def join(where: str, key: str) -> str:
    return f"{where}.{key}" if where else key


def location(where: str) -> str:
    return f"in {where}: " if where else ""
