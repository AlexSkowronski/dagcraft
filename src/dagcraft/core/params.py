"""
``${params.NAME}``, ``${env:NAME}`` and ``${run_date}`` references in pipeline files.

A string that is exactly one reference is replaced by the referenced value,
keeping its type, so ``${params.limit}`` can be a number or a list. A
reference inside a longer string is inserted as text. ``$${...}`` is a
literal ``${...}``.
"""

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from dagcraft.exceptions import ConfigError

REFERENCE = re.compile(r"(\$?)\$\{([^}]*)\}")
PARAM_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TEXT_TYPES = (str, int, float, date)


@dataclass(frozen=True)
class References:
    """
    What ``${...}`` refers to: the run date, and the params once resolved.

    ``params`` is ``None`` while the params themselves are being resolved,
    as params can't refer to each other.
    """

    run_date: date
    params: dict[str, Any] | None = None


def run_date_from(value: date | str | None) -> date:
    """
    The run date ``value`` gives: today if ``None``, or a date, or ISO text.

    Raises ``ConfigError`` for text that isn't a date.
    """
    if value is None:
        return date.today()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ConfigError(
            f"Run date '{value}' isn't a date: write it as YYYY-MM-DD, such as "
            "2026-10-17."
        ) from None


def resolve_params(
    declared: dict[str, Any],
    overrides: dict[str, Any],
    run_date: date,
) -> dict[str, Any]:
    """
    Combine the file's params with overrides.

    Params may reference environment variables and the run date, but not
    each other. Overrides must name a param declared in the file.
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
            values[name] = substitute(value, References(run_date))
        except ValueError as exc:
            raise ConfigError(f"Parameter '{name}': {exc}") from exc

    return values


def substitute(value: Any, references: References, where: str = "") -> Any:
    """
    Replace references in every string inside ``value``.

    Raises ``ValueError`` naming the field (``where``) with the bad
    reference.
    """
    if isinstance(value, str):
        return substitute_text(value, references, where)

    if isinstance(value, dict):
        return {
            key: substitute(item, references, join(where, str(key)))
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            substitute(item, references, f"{where}[{index}]")
            for index, item in enumerate(value)
        ]

    return value


def substitute_text(text: str, references: References, where: str) -> Any:
    """
    Replace the references in one string; see ``substitute``.
    """
    whole = REFERENCE.fullmatch(text)

    if whole is not None and not whole.group(1):
        return resolve(whole.group(2), references, where)

    def replace(match: re.Match[str]) -> str:
        if match.group(1):
            return match.group(0)[1:]

        value = resolve(match.group(2), references, where)

        if isinstance(value, bool) or not isinstance(value, TEXT_TYPES):
            # A config error, reported like the others.
            raise ValueError(  # noqa: TRY004
                f"{location(where)}${{{match.group(2)}}} is a "
                f"{type(value).__name__} and can only be used as a whole value, "
                "not inside text."
            )
        return str(value)

    return REFERENCE.sub(replace, text)


def resolve(reference: str, references: References, where: str) -> Any:
    """
    The value of one reference, written without its ``${`` and ``}``.
    """
    if reference == "run_date":
        return references.run_date

    if reference.startswith("env:"):
        name, has_default, default = reference.removeprefix("env:").partition(":-")
        value = os.environ.get(name)

        if value is not None:
            return value
        if has_default:
            return default

        raise ValueError(f"{location(where)}environment variable '{name}' is not set.")

    if reference.startswith("params."):
        params = references.params

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
        "understands. Use ${params.NAME}, ${env:NAME} or ${run_date}."
    )


def join(where: str, key: str) -> str:
    """
    The location of ``key`` inside ``where``, for error messages.
    """
    return f"{where}.{key}" if where else key


def location(where: str) -> str:
    """
    ``where`` as the start of an error message, if known.
    """
    return f"in {where}: " if where else ""
