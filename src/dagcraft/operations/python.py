"""
The python operation: your own function, as one step of a transform.
"""

from typing import Any

from dagcraft.imports import load_callable
from dagcraft.operations.base import register_operation


def import_function(options: dict[str, Any]) -> dict[str, Any]:
    """
    Import the function named by ``callable`` when the pipeline loads.
    """
    return {**options, "callable": load_callable(options["callable"])}


@register_operation("python", main="callable", prepare=import_function)
def python(data: Any, callable: Any, **args: Any) -> Any:  # noqa: A002 - as in python steps
    """
    Call ``callable`` (``module:function``) with the data and ``args``.

    The function gets the current table first, then ``args`` by name, and
    returns the table the next operation works on.
    """
    return callable(data, **args)
