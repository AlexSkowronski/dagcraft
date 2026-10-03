"""Checks for optional dependencies installed through dagcraft's extras."""

import importlib.util

from dagcraft.exceptions import ConfigError


def require_extra(
    *modules: str,
    extra: str,
    feature: str = "this connection type",
) -> None:
    """Raise ``ConfigError`` naming the extra to install if a module is missing."""
    missing = [module for module in modules if not module_available(module)]

    if missing:
        raise ConfigError(
            f"{feature} needs the '{extra}' extra "
            f"({', '.join(missing)} not installed). "
            f"Install it with: pip install 'dagcraft-pipelines[{extra}]'"
        )


def module_available(module: str) -> bool:
    """Whether ``module`` can be imported, without importing it."""
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        # Raised instead of returning None when a parent package is missing.
        return False
