"""
The ``dagcraft`` command's arguments.
"""

import argparse

from dagcraft import __version__


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the ``dagcraft`` command.
    """
    parser = argparse.ArgumentParser(
        prog="dagcraft",
        description="Check a pipeline, then run it.",
        epilog=(
            "Exit codes: 0 success, 1 a step or connection check failed, "
            "2 the pipeline file is invalid."
        ),
    )
    parser.add_argument(
        "config",
        help="Path to the pipeline YAML file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check the pipeline and show the steps it would run, without running.",
    )
    parser.add_argument(
        "--check-connections",
        action="store_true",
        help=(
            "Check the pipeline and prove each connection it uses works, "
            "without running."
        ),
    )
    parser.add_argument(
        "--max-workers",
        type=positive_int,
        metavar="N",
        help="Run up to N independent steps at once (overrides the file).",
    )
    parser.add_argument(
        "--run-id",
        help="ID for this run in the logs, e.g. from an orchestrator. Random if unset.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Skip every remaining step after the first failure.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also log detail, such as each file and each SQL partition read.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def positive_int(text: str) -> int:
    """
    Parse a whole number of at least 1, for ``--max-workers``.
    """
    try:
        value = int(text)
    except ValueError:
        value = 0

    if value < 1:
        raise argparse.ArgumentTypeError(
            f"expected a whole number of at least 1, got '{text}'"
        )
    return value
