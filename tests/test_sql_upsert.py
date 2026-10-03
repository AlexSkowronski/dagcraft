import logging

import pandas as pd
import pytest
import sqlalchemy as sa

from dagcraft import ConfigError, Pipeline, RunError


def upsert(tmp_path, rows, *, keys=("id",), columns=("id", "name"), **write):
    pd.DataFrame(rows, columns=list(columns)).to_csv(tmp_path / "rows.csv", index=False)
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "upsert"},
            "connections": {"db": {"type": "sql", "url": "sqlite:///warehouse.db"}},
            "steps": [
                {"id": "rows", "type": "read", "path": "rows.csv"},
                {
                    "id": "save",
                    "type": "write",
                    "connection": "db",
                    "table": "people",
                    "if_exists": "upsert",
                    "keys": list(keys),
                    "inputs": {"data": "rows"},
                    **write,
                },
            ],
        },
        base_dir=tmp_path,
    ).run()


def run_sql(tmp_path, sql):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")
    try:
        with engine.begin() as connection:
            result = connection.execute(sa.text(sql))
            return result.all() if result.returns_rows else []
    finally:
        engine.dispose()


def tables(tmp_path):
    rows = run_sql(tmp_path, "SELECT name FROM sqlite_master WHERE type = 'table'")
    return sorted(name for (name,) in rows)


def test_creates_a_missing_table(tmp_path):
    upsert(tmp_path, [(1, "Ada"), (2, "Grace")])

    assert run_sql(tmp_path, "SELECT id, name FROM people ORDER BY id") == [
        (1, "Ada"),
        (2, "Grace"),
    ]


def test_replaces_matching_rows_and_adds_the_rest(tmp_path, caplog):
    run_sql(tmp_path, "CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)")
    run_sql(tmp_path, "INSERT INTO people VALUES (1, 'Ada'), (2, 'Grace')")

    with caplog.at_level(logging.INFO, logger="dagcraft"):
        upsert(tmp_path, [(2, "Grace Hopper"), (3, "Linus")])

    assert run_sql(tmp_path, "SELECT id, name FROM people ORDER BY id") == [
        (1, "Ada"),
        (2, "Grace Hopper"),
        (3, "Linus"),
    ]
    assert "save: upserted into people: 1 rows replaced, 1 added" in caplog.text
    # The staging table is gone, and the table's definition is kept.
    assert tables(tmp_path) == ["people"]
    [(definition,)] = run_sql(
        tmp_path, "SELECT sql FROM sqlite_master WHERE name = 'people'"
    )
    assert "PRIMARY KEY" in definition


def test_running_twice_changes_nothing(tmp_path):
    rows = [(1, "Ada"), (2, "Grace")]
    upsert(tmp_path, rows)
    upsert(tmp_path, rows)

    assert run_sql(tmp_path, "SELECT COUNT(*) FROM people") == [(2,)]


def test_composite_keys(tmp_path):
    columns = ("region", "month", "sales")
    upsert(
        tmp_path,
        [("N", 1, 10), ("N", 2, 20)],
        keys=("region", "month"),
        columns=columns,
    )
    upsert(
        tmp_path, [("N", 2, 25), ("S", 2, 5)], keys=("region", "month"), columns=columns
    )

    assert run_sql(tmp_path, "SELECT * FROM people ORDER BY region, month") == [
        ("N", 1, 10),
        ("N", 2, 25),
        ("S", 2, 5),
    ]


def test_failure_leaves_the_table_and_schema_unchanged(tmp_path):
    run_sql(tmp_path, "CREATE TABLE people (id INTEGER, name TEXT NOT NULL)")
    run_sql(tmp_path, "INSERT INTO people VALUES (1, 'Ada')")

    # Row 1 would replace Ada, then row 2's missing name fails the insert.
    with pytest.raises(RunError, match="NOT NULL"):
        upsert(tmp_path, [(1, "Ada Lovelace"), (2, None)])

    assert run_sql(tmp_path, "SELECT id, name FROM people") == [(1, "Ada")]
    assert tables(tmp_path) == ["people"]


@pytest.mark.parametrize(
    ("rows", "keys", "message"),
    [
        ([(1, "Ada")], ("person_id",), "Upsert keys not in the data: person_id."),
        (
            [(1, "Ada"), (None, "Grace")],
            ("id",),
            "1 rows have no value in a key column (id), so they can't be matched.",
        ),
        (
            [(1, "Ada"), (1, "Grace")],
            ("id",),
            "2 rows share their keys with another row, such as id=1.",
        ),
    ],
)
def test_keys_must_identify_each_row(tmp_path, rows, keys, message):
    with pytest.raises(RunError) as exc_info:
        upsert(tmp_path, rows, keys=keys)

    assert message in str(exc_info.value)
    assert tables(tmp_path) == []


def test_columns_must_exist_in_the_table(tmp_path):
    run_sql(tmp_path, "CREATE TABLE people (id INTEGER, name TEXT)")

    with pytest.raises(RunError, match="Table people has no column nickname"):
        upsert(tmp_path, [(1, "Ada", "A")], columns=("id", "name", "nickname"))


@pytest.mark.parametrize(
    ("write", "message"),
    [
        ({"keys": []}, "if_exists: upsert needs 'keys'"),
        ({"keys": ["id", "id"]}, "'keys' should be distinct column names."),
        ({"if_exists": "append"}, "'keys' only applies to if_exists: upsert."),
    ],
)
def test_options_are_validated(tmp_path, write, message):
    with pytest.raises(ConfigError) as exc_info:
        upsert(tmp_path, [(1, "Ada")], **write)

    assert message in str(exc_info.value)


def test_dry_run_names_the_keys(tmp_path):
    pd.DataFrame({"id": [1]}).to_csv(tmp_path / "rows.csv", index=False)
    pipeline = Pipeline.from_dict(
        {
            "pipeline": {"name": "upsert"},
            "connections": {"db": {"type": "sql", "url": "sqlite:///warehouse.db"}},
            "steps": [
                {"id": "rows", "type": "read", "path": "rows.csv"},
                {
                    "id": "save",
                    "type": "write",
                    "connection": "db",
                    "table": "dbo.people",
                    "if_exists": "upsert",
                    "keys": ["region", "month"],
                    "inputs": {"data": "rows"},
                },
            ],
        },
        base_dir=tmp_path,
    )

    assert pipeline.plan()[1].description == (
        "write table dbo.people (if it exists: upsert by region, month) to 'db'"
    )
