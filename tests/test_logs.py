import logging
import threading

import pandas as pd
import pytest

from dagcraft import get_logger
from dagcraft.logs import describe_data, run_context, step_context

logger = get_logger("dagcraft.tests")


def last_record(caplog):
    return caplog.records[-1]


@pytest.fixture(autouse=True)
def capture(caplog):
    caplog.set_level(logging.INFO, logger="dagcraft")


def test_outside_a_run_messages_are_unchanged(caplog):
    logger.info("plain")

    record = last_record(caplog)
    assert record.getMessage() == "plain"
    assert (record.pipeline, record.run_id, record.step) == ("", "", "")


def test_messages_name_the_run_and_step(caplog):
    with run_context("sales", "abc123"):
        logger.info("starting")

        with step_context("orders"):
            logger.info("reading %d files", 3)

        logger.info("done")

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "[sales abc123] starting",
        "[sales abc123] orders: reading 3 files",
        "[sales abc123] done",
    ]
    assert caplog.records[1].step == "orders"


def test_new_threads_start_without_the_context(caplog):
    with run_context("sales", "abc123"):
        thread = threading.Thread(target=logger.info, args=("from a thread",))
        thread.start()
        thread.join()

    assert last_record(caplog).getMessage() == "from a thread"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pd.DataFrame({"a": range(1234), "b": 0}), "1,234 rows x 2 columns"),
        ({"North": pd.DataFrame(), "South": pd.DataFrame()}, "2 tables (North, South)"),
        (None, "no output"),
        (42, "int"),
    ],
)
def test_describe_data(value, expected):
    assert describe_data(value) == expected
