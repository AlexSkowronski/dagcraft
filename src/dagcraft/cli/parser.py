"""
The ``dagcraft`` command's arguments.
"""

import argparse
from typing import Any

import yaml

from dagcraft import __version__
from dagcraft.yaml_loader import load_yaml


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
        nargs="?",
        help="Path to the pipeline YAML file.",
    )
    parser.add_argument(
        "--schema",
        metavar="DIR",
        help=(
            "Write JSON Schemas for pipeline files to DIR, for autocomplete in "
            "editors, instead of running a pipeline."
        ),
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
        "--param",
        action="append",
        type=param,
        dest="params",
        metavar="NAME=VALUE",
        help=(
            "Set a param for this run; repeat for more. VALUE is read as YAML, "
            "as if written in the file, so 10 is a number and [a, b] a list."
        ),
    )
    parser.add_argument(
        "--run-date",
        metavar="YYYY-MM-DD",
        help=(
            "The date ${run_date} stands for, such as a day to load again. "
            "Today if unset."
        ),
    )
    parser.add_argument(
        "--max-workers",
        type=int,
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


def param(text: str) -> tuple[str, Any]:
    """
    A ``NAME=VALUE`` argument's name, and its value read as YAML.
    """
    name, equals, value = text.partition("=")

    if not equals or not name:
        raise argparse.ArgumentTypeError(
            f"'{text}' should be NAME=VALUE, such as region=north"
        )

    try:
        return name, load_yaml(value) if value else ""
    except yaml.YAMLError:
        raise argparse.ArgumentTypeError(
            f"the value in '{text}' isn't valid YAML"
        ) from None
