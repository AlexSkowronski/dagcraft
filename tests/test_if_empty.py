import logging

import pandas as pd
import pytest
import sqlalchemy as sa

from dagcraft import Pipeline, RunError, StepStatus
from dagcraft.cli import main


@pytest.fixture(autouse=True)
def files(tmp_path):
    (tmp_path / "events").mkdir()
    pd.DataFrame({"path": pd.Series([], dtype="string")}).to_csv(
        tmp_path / "none.csv", index=False
    )


def pipeline(tmp_path, read, **fields):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "empty"},
            "steps": [
                {"id": "events", "type": "read", **read, **fields},
                {
                    "id": "clean",
                    "type": "transform",
                    "inputs": {"data": "events"},
                    "operations": ["drop_nulls"],
                },
                {
                    "id": "other",
                    "type": "read",
                    "path": "none.csv",
                    "if_empty": "continue",
                },
            ],
        },
        base_dir=tmp_path,
    )


WILDCARD = {"path": "events/*.csv"}


def test_finding_nothing_fails_by_default(tmp_path):
    with pytest.raises(RunError) as exc_info:
        pipeline(tmp_path, WILDCARD).run()

    message = str(exc_info.value)
    assert (
        "failed at step 'events': Found nothing in events/*.csv from 'local'" in message
    )
    assert "set if_empty to stop" in message


def test_stop_skips_what_needs_it_and_still_succeeds(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="dagcraft"):
        result = pipeline(tmp_path, WILDCARD, if_empty="stop").run()

    assert result.success
    assert result.steps["events"].status == StepStatus.SUCCESS
    assert result.steps["events"].found_nothing == "events/*.csv from 'local'"
    assert result.steps["clean"].status == StepStatus.SKIPPED
    # Steps that don't need it still run.
    assert result.steps["other"].status == StepStatus.SUCCESS
    assert "events: found nothing: events/*.csv from 'local'" in caplog.text
    assert "clean: skipped: 'events' found nothing" in caplog.text
    assert "but stopped early: 'events' found nothing" in caplog.text


def test_continue_carries_on_with_the_empty_result(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="dagcraft"):
        result = pipeline(tmp_path, WILDCARD, if_empty="continue").run()

    assert result.steps["clean"].status == StepStatus.SUCCESS
    assert result.output("clean").empty
    assert "found nothing in events/*.csv from 'local'; carrying on" in caplog.text


def test_an_empty_list_of_paths_says_so(tmp_path):
    with pytest.raises(RunError, match="the files 'listing' lists: it listed none"):
        Pipeline.from_dict(
            {
                "pipeline": {"name": "empty"},
                "steps": [
                    {
                        "id": "listing",
                        "type": "read",
                        "path": "none.csv",
                        "if_empty": "continue",
                    },
                    {"id": "files", "type": "read", "inputs": {"paths": "listing"}},
                ],
            },
            base_dir=tmp_path,
        ).run()


def test_a_query_with_no_rows_counts_as_nothing(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE pending (path TEXT)"))
    engine.dispose()

    with pytest.raises(RunError, match="Found nothing in table pending from 'db'"):
        Pipeline.from_dict(
            {
                "pipeline": {"name": "empty"},
                "connections": {"db": {"type": "sql", "url": "sqlite:///db.sqlite"}},
                "steps": [
                    {
                        "id": "pending",
                        "type": "read",
                        "connection": "db",
                        "table": "pending",
                    }
                ],
            },
            base_dir=tmp_path,
        ).run()


def test_nothing_found_is_never_retried(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("dagcraft.core.step_runner.time.sleep", sleeps.append)

    result = pipeline(tmp_path, WILDCARD, if_empty="stop", retries=3).run()

    assert result.steps["events"].attempts == 1
    assert sleeps == []


def test_the_command_reports_an_early_stop(tmp_path, caplog):
    (tmp_path / "pipeline.yaml").write_text(
        "pipeline: {name: empty}\n"
        "steps:\n"
        "  - {id: events, type: read, path: 'events/*.csv', if_empty: stop}\n"
        "  - id: clean\n"
        "    type: transform\n"
        "    inputs: {data: events}\n"
        "    operations: [drop_nulls]\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        assert main([str(tmp_path / "pipeline.yaml")]) == 0

    report = [r for r in caplog.records if r.name == "dagcraft.cli.report"]
    lines = [record.getMessage() for record in report]
    assert any(line.startswith("EMPTY      events") for line in lines)
    assert any(line.startswith("SKIPPED    clean") for line in lines)
    assert lines[-1].endswith("but stopped early: 'events' found nothing")
    assert report[-1].levelno == logging.WARNING
