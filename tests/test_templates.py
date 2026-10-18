"""
Jinja templates in the fields that say what to read and write, and in query files.
"""

import sys
import types
from datetime import timedelta

import pandas as pd
import pytest
import sqlalchemy as sa

from dagcraft import ConfigError, Pipeline, template_function
from dagcraft.exceptions import RegistryError


@template_function
def dagcraft_test_week_start(day):
    return day - timedelta(days=day.weekday())


@pytest.fixture
def orders_db(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "region": ["north", "south", "north"],
            "amount": [10, 20, 30],
        }
    ).to_sql("orders", engine, index=False)
    engine.dispose()


def load(*steps, params=None):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "templates"},
            "params": params or {},
            "connections": {"db": {"type": "sql", "url": "sqlite:///db.sqlite"}},
            "steps": list(steps),
        },
        run_date="2026-10-17",
    )


def ids(pipeline, step="orders"):
    return pipeline.run().output(step)["order_id"].tolist()


def test_a_path_can_lay_out_the_run_date(tmp_path):
    (tmp_path / "raw" / "2026" / "10" / "17").mkdir(parents=True)
    pd.DataFrame({"order_id": [1]}).to_csv(
        tmp_path / "raw" / "2026" / "10" / "17" / "a.csv", index=False
    )
    pipeline = load(
        {
            "id": "orders",
            "type": "read",
            "path": "raw/{{ run_date.strftime('%Y/%m/%d') }}/*.csv",
        }
    )

    # The plan shows the path as it was rendered.
    assert pipeline.plan()[0].description == "read raw/2026/10/17/*.csv from 'local'"
    assert ids(pipeline) == [1]


def test_a_path_written_to_is_a_template(tmp_path):
    pd.DataFrame({"order_id": [1]}).to_csv(tmp_path / "in.csv", index=False)

    load(
        {"id": "orders", "type": "read", "path": "in.csv"},
        {
            "id": "save",
            "type": "write",
            "path": "out/orders_{{ run_date - timedelta(days=1) }}.csv",
            "inputs": {"data": "orders"},
        },
    ).run()

    assert (tmp_path / "out" / "orders_2026-10-16.csv").exists()


@pytest.mark.usefixtures("orders_db")
@pytest.mark.parametrize(("region", "expected"), [("north", [1, 3]), ("", [1, 2, 3])])
def test_a_query_can_leave_out_a_filter(region, expected):
    pipeline = load(
        {
            "id": "orders",
            "type": "read",
            "connection": "db",
            "query": (
                "SELECT order_id FROM orders "
                "{% if params.region %}WHERE region = :region{% endif %} "
                "ORDER BY order_id"
            ),
            # The value is still a bound parameter, never pasted into the SQL.
            "params": {"region": "${params.region}"},
        },
        params={"region": region},
    )

    assert ids(pipeline) == expected


@pytest.mark.usefixtures("orders_db")
def test_a_query_file_is_a_template(tmp_path):
    (tmp_path / "sql").mkdir()
    (tmp_path / "sql" / "orders.sql").write_text(
        "SELECT {{ params.columns | join(', ') }}\n"
        "FROM orders\n"
        "WHERE amount >= :minimum\n",
        encoding="utf-8",
    )
    pipeline = load(
        {
            "id": "orders",
            "type": "read",
            "connection": "db",
            "query_file": "sql/orders.sql",
            "params": {"minimum": 20},
        },
        params={"columns": ["order_id", "amount"]},
    )

    output = pipeline.run().output("orders")

    assert output.columns.tolist() == ["order_id", "amount"]
    assert output["order_id"].tolist() == [2, 3]


@pytest.mark.usefixtures("orders_db")
def test_tables_are_templates(tmp_path):
    load(
        {"id": "orders", "type": "read", "connection": "db", "table": "orders"},
        {
            "id": "save",
            "type": "write",
            "connection": "db",
            "table": "orders_{{ run_date.year }}",
            "inputs": {"data": "orders"},
        },
        {
            "id": "back",
            "type": "read",
            "connection": "db",
            "table": "orders_{{ run_date.year }}",
            "after": ["save"],
        },
    ).run()

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    assert sa.inspect(engine).has_table("orders_2026")
    engine.dispose()


def test_your_functions_and_environment_variables_can_be_used(tmp_path, monkeypatch):
    monkeypatch.setenv("DAGCRAFT_TEST_FOLDER", "raw")
    (tmp_path / "raw").mkdir()
    pd.DataFrame({"order_id": [1]}).to_csv(
        tmp_path / "raw" / "week_2026-10-12.csv", index=False
    )

    pipeline = load(
        {
            "id": "orders",
            "type": "read",
            "path": (
                "{{ env.DAGCRAFT_TEST_FOLDER }}/"
                "week_{{ dagcraft_test_week_start(run_date) }}.csv"
            ),
        }
    )

    assert ids(pipeline) == [1]


def test_other_fields_are_left_as_written(monkeypatch):
    module = types.ModuleType("dagcraft_test_templates")
    monkeypatch.setattr(module, "echo", lambda text: text, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    pipeline = load(
        {
            "id": "echo",
            "type": "python",
            "callable": "dagcraft_test_templates:echo",
            "args": {"text": "Hello {{ name }}"},
        }
    )

    assert pipeline.run().output("echo") == "Hello {{ name }}"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        (
            "{{ params.regin }}/orders.csv",
            "Step 'orders': in path: 'dict object' has no attribute 'regin'",
        ),
        ("{{ nothing }}/orders.csv", "Step 'orders': in path: 'nothing' is undefined"),
        ("{{ run_date }/orders.csv", "Step 'orders': in path: line 1: unexpected '}'"),
    ],
)
def test_a_template_that_fails_says_where(path, message):
    with pytest.raises(ConfigError) as exc_info:
        load({"id": "orders", "type": "read", "path": path}, params={"region": "north"})

    assert str(exc_info.value) == message


def test_a_query_file_that_fails_names_the_file(tmp_path):
    (tmp_path / "bad.sql").write_text(
        "SELECT {{ columns }} FROM orders\n", encoding="utf-8"
    )

    with pytest.raises(
        ConfigError, match=r"Step 'orders': in bad\.sql: 'columns' is undefined"
    ):
        load(
            {
                "id": "orders",
                "type": "read",
                "connection": "db",
                "query_file": "bad.sql",
            }
        )


def test_your_functions_cant_take_a_name_templates_already_have():
    def params():
        return {}

    with pytest.raises(RegistryError, match="The name 'params' is already taken"):
        template_function(params)
