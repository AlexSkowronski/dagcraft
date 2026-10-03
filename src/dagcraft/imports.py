"""
Importing your own code from the project, for ``python`` steps and operations.
"""

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dagcraft.exceptions import ConfigError


def make_importable(directory: Path) -> None:
    """
    Let ``import`` find modules in ``directory``, as it does a script's folder.

    ``python main.py`` and ``python -m`` put the current folder on the import
    path, but the ``dagcraft`` command's launcher doesn't, so ``callable:
    my_functions:parse`` would fail there without this. The folder goes
    first, like a script's, and is added once.
    """
    folder = str(directory.resolve())

    if folder not in sys.path:
        sys.path.insert(0, folder)


def load_callable(path: str) -> Callable[..., Any]:
    """
    Import ``module.path:function`` and return the function.
    """
    if ":" not in path:
        raise ConfigError(
            "Python callable must use the format 'module.path:function_name'."
        )

    module_name, function_name = path.split(":", maxsplit=1)

    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"Could not import module '{module_name}'.") from exc

    function = getattr(module, function_name, None)

    if function is None:
        raise ConfigError(
            f"Module '{module_name}' has no callable named '{function_name}'."
        )

    if not callable(function):
        raise ConfigError(f"'{path}' is not callable.")

    return function
