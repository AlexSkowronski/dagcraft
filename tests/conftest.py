import logging

import pytest


@pytest.fixture(autouse=True)
def reset_dagcraft_log_level():
    """
    The command line sets the dagcraft logger's level; undo it after each test.
    """
    yield
    logging.getLogger("dagcraft").setLevel(logging.NOTSET)
