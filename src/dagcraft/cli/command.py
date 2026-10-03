"""
The ``dagcraft`` command: check a pipeline file, then run it.
"""

import argparse
import logging
from enum import IntEnum
from pathlib import Path

from dagcraft.cli import report
from dagcraft.cli.parser import build_parser
from dagcraft.config import RunOptions
from dagcraft.core.pipeline import Pipeline
from dagcraft.exceptions import ConfigError, RunError
from dagcraft.logs import configure_logging, get_logger
from dagcraft.schema import write_schemas

logger = get_logger(__name__)


class ExitCode(IntEnum):
    """
    What the command's exit status means, for schedulers and scripts.
    """

    SUCCESS = 0
    FAILED = 1
    INVALID = 2


def main(argv: list[str] | None = None) -> int:
    """
    Run the command with ``argv`` (the process's arguments by default).

    Returns the exit code: see ``ExitCode``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)

    if args.schema is not None:
        return schema(Path(args.schema))
    if args.config is None:
        parser.error("the following arguments are required: config")

    try:
        # Check the options first: they're cheap, and loading isn't.
        options = run_options(args)
        pipeline = Pipeline.from_yaml(args.config)
    except ConfigError as exc:
        # A problem with the options or the file: the message, no traceback.
        logger.error("%s", exc)  # noqa: TRY400
        return ExitCode.INVALID

    report.log_valid(pipeline)

    if args.dry_run or args.check_connections:
        return check(pipeline, args, options)
    return run(pipeline, options)


def schema(folder: Path) -> ExitCode:
    """
    Write the JSON Schemas for editors, including your own components.
    """
    for path in write_schemas(folder):
        logger.info("Wrote %s", path)
    return ExitCode.SUCCESS


def run_options(args: argparse.Namespace) -> RunOptions:
    """
    The run's options from the arguments, checked like ``Pipeline.run``'s.
    """
    return RunOptions.parse(
        fail_fast=args.fail_fast,
        run_id=args.run_id,
        # The command line never reads outputs, so don't keep them.
        keep_outputs=False,
        max_workers=args.max_workers,
    )


def check(
    pipeline: Pipeline,
    args: argparse.Namespace,
    options: RunOptions,
) -> ExitCode:
    """
    Show the plan and/or check the connections, without running.
    """
    if args.dry_run:
        report.log_plan(pipeline, options.max_workers)

    if args.check_connections and not report.log_checks(pipeline):
        return ExitCode.FAILED
    return ExitCode.SUCCESS


def run(pipeline: Pipeline, options: RunOptions) -> ExitCode:
    """
    Run the pipeline and log a summary of every step.
    """
    try:
        result = pipeline.run(**options.model_dump())
    except RunError as exc:
        report.log_summary(exc.result)
        return ExitCode.FAILED

    report.log_summary(result)
    return ExitCode.SUCCESS
