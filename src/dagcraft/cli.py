"""Command-line interface for dagcraft."""

from __future__ import annotations

import argparse
import io
import logging
import sys
from typing import Any

import yaml

from dagcraft.core.config import load_yaml
from dagcraft.core.pipeline import Pipeline
from dagcraft.core.runtime import PipelineResult
from dagcraft.exceptions import DagcraftError, PipelineError

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``dagcraft`` command."""
    parser = argparse.ArgumentParser(
        prog="dagcraft",
        description="Config-driven DAG pipelines for Python.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # Arguments shared by every command.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "pipeline",
        help="Path to the pipeline YAML file.",
    )
    common.add_argument(
        "--param",
        dest="params",
        metavar="NAME=VALUE",
        type=parse_param,
        action="append",
        default=[],
        help="Override a param from the file. Values are read as YAML. Repeatable.",
    )

    subparsers.add_parser(
        "validate",
        parents=[common],
        help="Validate a pipeline.",
    )
    run_parser = subparsers.add_parser(
        "run",
        parents=[common],
        help="Run a pipeline.",
    )
    run_parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Skip every remaining step after the first failure.",
    )
    return parser


def parse_param(text: str) -> tuple[str, Any]:
    name, equals, value = text.partition("=")

    if not equals or not name:
        raise argparse.ArgumentTypeError(f"expected NAME=VALUE, got '{text}'")

    if not value:
        return name, ""

    try:
        return name, load_yaml(io.StringIO(value))
    except yaml.YAMLError as exc:
        raise argparse.ArgumentTypeError(
            f"can't read the value of '{name}': {exc}"
        ) from exc


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        pipeline = Pipeline.from_yaml(
            args.pipeline,
            params=dict(args.params),
        )
    except DagcraftError as exc:
        # User-facing config error: show the message, not a traceback.
        logger.error("%s", exc)  # noqa: TRY400
        sys.exit(1)

    if args.command == "validate":
        pipeline.validate()
        logger.info(
            "Pipeline '%s' is valid.",
            pipeline.config.pipeline.name,
        )
        return

    if args.command == "run":
        try:
            result = pipeline.run(fail_fast=args.fail_fast)
        except PipelineError as exc:
            log_summary(exc.result)
            sys.exit(1)

        log_summary(result)


def log_summary(result: PipelineResult) -> None:
    logger.info("Pipeline: %s", result.name)
    logger.info("-" * 50)

    for step in result.steps.values():
        logger.info(
            "%-10s %-25s %.3fs",
            step.status.value,
            step.id,
            step.duration,
        )

    logger.info("-" * 50)

    if result.success:
        logger.info(
            "SUCCESS in %.3fs",
            result.duration,
        )
    else:
        logger.error(
            "FAILED in %.3fs",
            result.duration,
        )


if __name__ == "__main__":
    main()
