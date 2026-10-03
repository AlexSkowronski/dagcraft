"""
Importing your own modules from the project, for ``python`` steps.
"""

import sys
from pathlib import Path


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
