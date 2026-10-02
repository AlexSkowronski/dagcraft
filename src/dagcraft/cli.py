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

    run_parser = subparsers.add_parser(
        "run",
        help="Check a pipeline, then run it.",
    )
    run_parser.add_argument(
        "pipeline",
        help="Path to the pipeline YAML file.",
    )
    run_parser.add_argument(
        "--param",
        dest="params",
        metavar="NAME=VALUE",
        type=parse_param,
        action="append",
        default=[],
        help="Override a param from the file. Values are read as YAML. Repeatable.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check the pipeline and show the steps it would run, without running.",
    )
    run_parser.add_argument(
        "--check-connections",
        action="store_true",
        help=(
            "Check the pipeline and prove each connection it uses works, "
            "without running."
        ),
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

    if args.dry_run or args.check_connections:
        if args.dry_run:
            log_plan(pipeline)
        else:
            logger.info("Pipeline '%s' is valid.", pipeline.config.pipeline.name)

        if args.check_connections and not log_checks(pipeline):
            sys.exit(1)
        return

    try:
        result = pipeline.run(fail_fast=args.fail_fast)
    except PipelineError as exc:
        log_summary(exc.result)
        sys.exit(1)

    log_summary(result)


def log_checks(pipeline: Pipeline) -> bool:
    """Check the pipeline's connections and log the outcome. True if all pass."""
    names = pipeline.connections_in_use()
    logger.info("Checking %d connection(s):", len(names))

    checks = pipeline.check_connections()
    name_width = max((len(check.name) for check in checks), default=0)
    type_width = max((len(check.type) for check in checks), default=0)

    for check in checks:
        logger.log(
            logging.INFO if check.ok else logging.ERROR,
            "  %-*s  %-*s  %-6s  %s",
            name_width,
            check.name,
            type_width,
            check.type,
            "OK" if check.ok else "FAILED",
            check.message,
        )

    failed = sum(not check.ok for check in checks)

    if failed:
        logger.error("%d of %d connection(s) failed.", failed, len(checks))
        return False

    logger.info("All connections work.")
    return True


def log_plan(pipeline: Pipeline) -> None:
    logger.info("Pipeline '%s' is valid.", pipeline.config.pipeline.name)

    if pipeline.params:
        params = ", ".join(f"{name}={value}" for name, value in pipeline.params.items())
        logger.info("Params: %s", params)

    plan = pipeline.plan()
    width = max((len(step.id) for step in plan), default=0)
    logger.info("Steps, in run order:")

    for number, step in enumerate(plan, start=1):
        inputs = ", ".join(f"{name}: {source}" for name, source in step.inputs.items())
        logger.info(
            "%3d. %-*s  %s%s",
            number,
            width,
            step.id,
            step.description,
            f"  <- {inputs}" if inputs else "",
        )

    logger.info("Dry run: nothing was run.")


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
