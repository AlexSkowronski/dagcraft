from typing import Any

import pandas as pd
import pytest
import sqlalchemy as sa

from dagcraft import ConfigError, Pipeline, PipelineError
from dagcraft.connections import base as connections_base


def make_pipeline(*steps, connections, base_dir):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "test"},
            "connections": connections,
            "steps": list(steps),
        },
        base_dir=base_dir,
    )


def database(name="warehouse.db"):
    """A SQLite connection with a path relative to the pipeline directory."""
    return {"db": {"type": "sql", "url": f"sqlite:///{name}"}}


def write_rows(tmp_path, rows, *, table="scores", **write):
    pd.DataFrame(rows, columns=["name", "score"]).to_csv(
        tmp_path / "rows.csv", index=False
    )
    return make_pipeline(
        {"id": "rows", "type": "read", "path": "rows.csv"},
        {
            "id": "save",
            "type": "write",
            "connection": "db",
            "table": table,
            "inputs": {"data": "rows"},
            **write,
        },
        connections=database(),
        base_dir=tmp_path,
    ).run()


def query(tmp_path, sql):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")
    try:
        with engine.connect() as connection:
            return connection.execute(sa.text(sql)).all()
    finally:
        engine.dispose()


def execute(tmp_path, sql):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(sql))
    finally:
        engine.dispose()


def test_write_then_read_by_table_and_query(tmp_path):
    write_rows(tmp_path, [("Ada", 9), ("Grace", 7), ("Alan", 4)])

    # The relative SQLite path is resolved against the pipeline directory.
    assert (tmp_path / "warehouse.db").exists()

    result = make_pipeline(
        {"id": "everyone", "type": "read", "connection": "db", "table": "scores"},
        {
            "id": "top",
            "type": "read",
            "connection": "db",
            "query": "SELECT name FROM scores WHERE score > :minimum ORDER BY name",
            "params": {"minimum": 5},
        },
        connections=database(),
        base_dir=tmp_path,
    ).run()

    assert len(result.artifact("everyone")) == 3
    assert result.artifact("top")["name"].tolist() == ["Ada", "Grace"]


def test_writing_to_an_existing_table_fails_by_default(tmp_path):
    write_rows(tmp_path, [("Ada", 9)])

    with pytest.raises(PipelineError, match="already exists"):
        write_rows(tmp_path, [("Grace", 7)])


@pytest.mark.parametrize(
    ("if_exists", "expected"),
    [
        ("append", [("Ada", 9), ("Grace", 7)]),
        ("delete_rows", [("Grace", 7)]),
        ("replace", [("Grace", 7)]),
    ],
)
def test_if_exists(tmp_path, if_exists, expected):
    write_rows(tmp_path, [("Ada", 9)])
    write_rows(tmp_path, [("Grace", 7)], if_exists=if_exists)

    assert query(tmp_path, "SELECT name, score FROM scores ORDER BY rowid") == expected


@pytest.mark.parametrize(
    ("if_exists", "keeps_definition"),
    [("delete_rows", True), ("replace", False)],
)
def test_delete_rows_keeps_the_table_definition(tmp_path, if_exists, keeps_definition):
    execute(
        tmp_path, "CREATE TABLE scores (name TEXT, score INTEGER CHECK (score >= 0))"
    )

    write_rows(tmp_path, [("Ada", 9)], if_exists=if_exists)

    [(definition,)] = query(
        tmp_path, "SELECT sql FROM sqlite_master WHERE name = 'scores'"
    )
    assert ("CHECK" in definition) is keeps_definition


def test_failed_write_leaves_the_table_unchanged(tmp_path):
    execute(tmp_path, "CREATE TABLE scores (name TEXT NOT NULL, score INTEGER)")
    execute(tmp_path, "INSERT INTO scores VALUES ('Ada', 9)")

    # The second row violates NOT NULL; with one row per batch, the first
    # batch has already been inserted when the error happens.
    with pytest.raises(PipelineError):
        write_rows(
            tmp_path,
            [("Grace", 7), (None, 5)],
            if_exists="append",
            args={"chunksize": 1},
        )

    assert query(tmp_path, "SELECT name FROM scores") == [("Ada",)]


def test_url_can_come_from_an_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("WAREHOUSE_URL", f"sqlite:///{tmp_path / 'warehouse.db'}")
    execute(tmp_path, "CREATE TABLE scores (name TEXT, score INTEGER)")

    result = make_pipeline(
        {"id": "scores", "type": "read", "connection": "db", "table": "scores"},
        connections={"db": {"type": "sql", "url_env": "WAREHOUSE_URL"}},
        base_dir=tmp_path,
    ).run()

    assert result.artifact("scores").empty


def test_missing_url_variable_fails_the_step(tmp_path):
    pipeline = make_pipeline(
        {"id": "scores", "type": "read", "connection": "db", "table": "scores"},
        connections={"db": {"type": "sql", "url_env": "WAREHOUSE_URL"}},
        base_dir=tmp_path,
    )

    with pytest.raises(PipelineError, match="'WAREHOUSE_URL', which is not set"):
        pipeline.run()


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (
            {"type": "read", "query": "SELECT 1", "table": "scores"},
            "Set exactly one of 'query' or 'table'.",
        ),
        (
            {"type": "read"},
            "Set exactly one of 'query' or 'table'.",
        ),
        (
            {"type": "read", "table": "scores", "params": {"a": 1}},
            "'params' can only be used with 'query'.",
        ),
        (
            {"type": "read", "table": "db.dbo.scores"},
            "should be written as 'name' or 'schema.name'",
        ),
        (
            {"type": "write", "table": "scores", "if_exists": "upsert"},
            "if_exists: Input should be 'fail', 'append', 'delete_rows' or 'replace'",
        ),
        (
            {"type": "write", "path": "scores.csv"},
            "table: Field required",
        ),
    ],
)
def test_step_validation(tmp_path, step, message):
    steps = [{"id": "source", "type": "read", "path": "in.csv"}]
    inputs: dict[str, Any] = {}
    if step["type"] == "write":
        inputs["inputs"] = {"data": "source"}
    steps.append({"id": "step", "connection": "db", **step, **inputs})

    with pytest.raises(ConfigError) as exc_info:
        make_pipeline(*steps, connections=database(), base_dir=tmp_path)

    assert message in str(exc_info.value)


def test_connection_needs_a_url(tmp_path):
    with pytest.raises(ConfigError, match="Set exactly one of 'url' or 'url_env'"):
        make_pipeline(connections={"db": {"type": "sql"}}, base_dir=tmp_path)


def test_missing_extra_is_a_config_error(tmp_path, monkeypatch):
    monkeypatch.setattr(connections_base, "module_available", lambda _module: False)

    with pytest.raises(ConfigError, match=r"pip install 'dagcraft\[sql\]'"):
        make_pipeline(connections=database(), base_dir=tmp_path)
