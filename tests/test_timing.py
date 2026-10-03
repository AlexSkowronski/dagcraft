import logging
import time

from dagcraft import Timer


def test_context_manager_measures_the_block():
    with Timer() as timer:
        time.sleep(0.01)
        during = timer.elapsed

    after = timer.elapsed
    time.sleep(0.01)

    assert 0 < during <= after
    # Fixed once the block ends.
    assert timer.elapsed == after


def test_elapsed_is_zero_before_starting():
    assert Timer().elapsed == 0.0


def test_logs_when_given_a_logger(caplog):
    with caplog.at_level(logging.INFO), Timer("load", logger=logging.getLogger("t")):
        pass

    [record] = caplog.records
    assert record.getMessage().startswith("load took ")


def test_decorator_times_each_call(caplog):
    @Timer(logger=logging.getLogger("t"))
    def double(value):
        return value * 2

    with caplog.at_level(logging.INFO):
        assert double(2) == 4
        assert double(3) == 6

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert all(
        message.startswith("test_decorator_times_each_call.<locals>.double took ")
        for message in messages
    )
