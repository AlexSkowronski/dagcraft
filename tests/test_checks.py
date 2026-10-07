"""
The check pipelines in config/checks work, and catch what they're meant to.

They run here against SQLite, in place of your database, by swapping in a
connections.yaml as you would to point them at your own.
"""

import shutil
from pathlib import Path

import pytest

from dagcraft import Pipeline, RunError

CHECK = Path(__file__).resolve().parents[1] / "config" / "checks" / "sql_server"


@pytest.fixture
def check(tmp_path, monkeypatch):
    """
    A copy of the SQL Server check, pointed at a SQLite file, run from inside.
    """
    folder = tmp_path / "sql_server"
    shutil.copytree(CHECK, folder)
    (folder / ".env").write_text("", encoding="utf-8")
    (folder / "connections.yaml").write_text(
        "connections:\n  warehouse: {type: sql, url: 'sqlite:///check.db'}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(folder)
    monkeypatch.delenv("CHECK_TABLE", raising=False)
    return folder


@pytest.mark.usefixtures("check")
def test_the_sql_server_check_passes_on_a_working_database():
    result = Pipeline.from_yaml("pipeline.yaml").run()

    assert result.success
    assert result.output("check_table")["order_id"].tolist() == [3, 4]


@pytest.mark.usefixtures("check")
def test_it_runs_again_on_the_table_it_left():
    Pipeline.from_yaml("pipeline.yaml").run()

    assert Pipeline.from_yaml("pipeline.yaml").run().success


def test_it_catches_an_upsert_that_went_wrong(check):
    # As if the upsert had kept the old amount for order 3.
    (check / "changes.csv").write_text(
        "order_id,amount,status\n3,30,shipped\n4,40,open\n", encoding="utf-8"
    )

    with pytest.raises(RunError) as exc_info:
        Pipeline.from_yaml("pipeline.yaml").run()

    # Both checks notice: the query finds no order over 100 any more, and
    # the table's order 3 has the wrong amount.
    steps = exc_info.value.result.steps
    assert "Found nothing in a query" in (steps["big_orders"].error or "")
    assert "has 1 rows, fewer than 2" in (steps["check_table"].error or "")
