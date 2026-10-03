import logging

import pytest


@pytest.fixture(autouse=True)
def run_from_tmp_path(tmp_path, monkeypatch):
    """
    Run each test from its own folder, as relative paths resolve from there.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def reset_dagcraft_log_level():
    """
    The command line sets the dagcraft logger's level; undo it after each test.
    """
    yield
    logging.getLogger("dagcraft").setLevel(logging.NOTSET)
