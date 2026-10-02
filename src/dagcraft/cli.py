"""Command-line interface for dagcraft."""

from __future__ import annotations

import argparse
import logging
import sys

from dagcraft.exceptions import DagcraftError
from dagcraft.pipeline import Pipeline

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
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a pipeline.",
    )
    validate_parser.add_argument(
        "pipeline",
        help="Path to the pipeline YAML file.",
    )
    run_parser = subparsers.add_parser(
        "run",
        help="Run a pipeline",
    )
    run_parser.add_argument("pipeline", help="Path to the pipeline YAML file.")
    return parser


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
        result = pipeline.run()
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
            return

        logger.error(
            "FAILED in %.3fs",
            result.duration,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
