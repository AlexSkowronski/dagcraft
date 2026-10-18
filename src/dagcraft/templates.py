"""
Jinja templates: the SQL and paths that say what a step reads or writes.

Readers and writers name their ``template_fields``, such as ``path`` or
``query``, and the SQL reader renders query files too. Everything else in a
pipeline file is left as written.
"""

import os
import re
from datetime import date, timedelta
from typing import Any

import jinja2

from dagcraft.exceptions import RegistryError
from dagcraft.registry import TEMPLATE_FUNCTIONS

# Text with none of these has nothing for Jinja to do.
TAG = re.compile(r"\{[{%#]")

# What every template can use; your functions can't take these names.
BUILT_IN = ("params", "env", "run_date", "timedelta")


class Templates:
    """
    Renders templates with the pipeline's params, the run date and your functions.

    Templates see ``params``, ``env`` (the environment variables),
    ``run_date`` and ``timedelta``, plus every function registered with
    ``template_function``. A name that isn't defined is an error, not blank
    text.
    """

    def __init__(self, params: dict[str, Any], run_date: date) -> None:
        # The output is SQL and paths, not HTML, so nothing is escaped. A
        # block tag on a line of its own, such as {% if %}, leaves no line.
        self.environment = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            autoescape=False,  # noqa: S701
        )
        self.environment.globals.update(dict(TEMPLATE_FUNCTIONS.items()))
        self.environment.globals.update(
            params=params,
            env=dict(os.environ),
            run_date=run_date,
            timedelta=timedelta,
        )

    def render(self, text: str, where: str) -> str:
        """
        ``text`` rendered, or as it is if it has no template tags.

        ``where`` names the field or file, for errors. Raises ``ValueError``
        for a template that's invalid or uses a name that isn't defined.
        """
        if not TAG.search(text):
            return text

        try:
            return self.environment.from_string(text).render()
        except jinja2.TemplateSyntaxError as exc:
            raise ValueError(f"in {where}: line {exc.lineno}: {exc.message}") from exc
        except jinja2.UndefinedError as exc:
            raise ValueError(f"in {where}: {exc.message}") from exc


def template_function(function):
    """
    Decorator that makes ``function`` callable in templates, by its name.

    The function is returned unchanged, so it can still be called and tested
    directly.
    """
    name = function.__name__

    if name in BUILT_IN:
        raise RegistryError(
            f"The name '{name}' is already taken by a value every template has."
        )

    TEMPLATE_FUNCTIONS.register(name)(function)
    return function
