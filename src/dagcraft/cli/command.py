"""The ``dagcraft`` command: check a pipeline file, then run it."""

import argparse
import logging
from enum import IntEnum

from dagcraft.cli import report
from dagcraft.cli.parser import build_parser
from dagcraft.core.pipeline import Pipeline
from dagcraft.exceptions import ConfigError, RunError
from dagcraft.logs import configure_logging, get_logger

logger = get_logger(__name__)


class ExitCode(IntEnum):
    """What the command's exit status means, for schedulers and scripts."""

    SUCCESS = 0
    FAILED = 1
    INVALID = 2


def main(argv: list[str] | None = None) -> int:
    """Run the command with ``argv`` (the process's arguments by default).

    Returns the exit code: see ``ExitCode``.
    """
    args = build_parser().parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)

    try:
        pipeline = Pipeline.from_yaml(args.config)
    except ConfigError as exc:
        # A problem with the file: show the message, not a traceback.
        logger.error("%s", exc)  # noqa: TRY400
        return ExitCode.INVALID

    report.log_valid(pipeline)

    if args.dry_run or args.check_connections:
        return check(pipeline, args)
    return run(pipeline, args)


def check(pipeline: Pipeline, args: argparse.Namespace) -> ExitCode:
    """Show the plan and/or check the connections, without running."""
    if args.dry_run:
        report.log_plan(pipeline, args.max_workers)

    if args.check_connections and not report.log_checks(pipeline):
        return ExitCode.FAILED
    return ExitCode.SUCCESS


def run(pipeline: Pipeline, args: argparse.Namespace) -> ExitCode:
    """Run the pipeline and log a summary of every step."""
    try:
        # The command line never reads outputs, so don't keep them.
        result = pipeline.run(
            fail_fast=args.fail_fast,
            run_id=args.run_id,
            keep_outputs=False,
            max_workers=args.max_workers,
        )
    except RunError as exc:
        report.log_summary(exc.result)
        return ExitCode.FAILED

    report.log_summary(result)
    return ExitCode.SUCCESS
