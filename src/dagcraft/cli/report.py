"""
What the ``dagcraft`` command logs about a pipeline: its plan, checks and outcome.
"""

import logging

from dagcraft.core.pipeline import Pipeline
from dagcraft.core.results import PipelineResult
from dagcraft.logs import get_logger

logger = get_logger(__name__)

RULE = "-" * 50


def log_valid(pipeline: Pipeline) -> None:
    """
    Say the pipeline file passed every check.
    """
    logger.info("Pipeline '%s' is valid.", pipeline.name)


def log_plan(pipeline: Pipeline, max_workers: int | None = None) -> None:
    """
    Log the params and the steps in run order, for a dry run.
    """
    if pipeline.params:
        params = ", ".join(f"{name}={value}" for name, value in pipeline.params.items())
        logger.info("Params: %s", params)

    plan = pipeline.plan()
    width = max((len(step.id) for step in plan), default=0)
    max_workers = max_workers or pipeline.max_workers

    if max_workers > 1:
        logger.info("Up to %d independent steps run at once.", max_workers)

    logger.info("Steps, in run order:")

    for number, step in enumerate(plan, start=1):
        needs = [f"{name}: {source}" for name, source in step.inputs.items()]
        needs += [f"after {source}" for source in step.after]
        logger.info(
            "%3d. %-*s  %s%s",
            number,
            width,
            step.id,
            step.description,
            f"  <- {', '.join(needs)}" if needs else "",
        )

    logger.info("Dry run: nothing was run.")


def log_checks(pipeline: Pipeline) -> bool:
    """
    Check the pipeline's connections and log a table of results.

    Returns whether every check passed.
    """
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


def log_summary(result: PipelineResult) -> None:
    """
    Log a table of every step's status and duration, then the outcome.
    """
    logger.info("Pipeline: %s (run %s)", result.name, result.run_id)
    logger.info(RULE)

    for step in result.steps.values():
        status = "EMPTY" if step.found_nothing else step.status.value
        logger.info("%-10s %-25s %.3fs", status, step.id, step.duration)

    logger.info(RULE)
    stopped = [f"'{step.id}' found nothing" for step in result.found_nothing]

    if not result.success:
        logger.error("FAILED in %.3fs", result.duration)
    elif stopped:
        logger.warning(
            "SUCCESS in %.3fs, but stopped early: %s",
            result.duration,
            "; ".join(stopped),
        )
    else:
        logger.info("SUCCESS in %.3fs", result.duration)
