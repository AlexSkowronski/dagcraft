"""
Turning pydantic validation errors into readable messages.
"""

from pydantic import ValidationError


def format_validation_error(exc: ValidationError) -> str:
    """
    Summarise a pydantic error as one line, one clause per problem.
    """
    problems = []

    for error in exc.errors():
        message = error["msg"].removeprefix("Value error, ")
        location = ".".join(str(part) for part in error["loc"])
        problems.append(f"{location}: {message}" if location else message)

    return "; ".join(problems)
