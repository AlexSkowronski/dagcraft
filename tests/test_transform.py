import logging
import re
import sys
import types

import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline, RunError, register_operation

ORDERS = pd.DataFrame(
    {
        "order_id": [1, 2, 3, 4],
        "customer_id": [10, 20, 10, None],
        "price": [5.0, 50.0, 20.0, 8.0],
        "quantity": [2, 1, 3, 1],
    }
)
CUSTOMERS = pd.DataFrame({"customer_id": [10, 20], "name": ["Ada", "Grace"]})


@pytest.fixture(autouse=True)
def data(tmp_path):
    ORDERS.to_csv(tmp_path / "orders.csv", index=False)
    CUSTOMERS.to_csv(tmp_path / "customers.csv", index=False)


def pipeline(tmp_path, *operations, inputs=None):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "chain"},
            "steps": [
                {"id": "orders", "type": "read", "path": "orders.csv"},
                {"id": "customers", "type": "read", "path": "customers.csv"},
                {
                    "id": "clean",
                    "type": "transform",
                    "inputs": inputs or {"data": "orders"},
                    "operations": list(operations),
                },
            ],
        },
        base_dir=tmp_path,
    )


def run(tmp_path, *operations, **kwargs):
    return pipeline(tmp_path, *operations, **kwargs).run().output("clean")


def test_operations_apply_in_order(tmp_path):
    frame = run(
        tmp_path,
        {"drop_nulls": ["customer_id"]},
        {"derive": {"total": "price * quantity"}},
        {"filter": "total > 15"},
        # After the first operation, the left side is the result so far.
        {"join": {"right": "customers", "on": "customer_id", "how": "left"}},
        {"sort": {"by": "total", "ascending": False}},
        {"select": ["order_id", "name", "total"]},
        {"check": {"not_null": ["name"], "unique": ["order_id"]}},
        inputs={"data": "orders", "customers": "customers"},
    )

    assert frame.to_dict("list") == {
        "order_id": [3, 2],
        "name": ["Ada", "Grace"],
        "total": [60.0, 50.0],
    }


def test_a_join_that_starts_the_transform_names_both_sides(tmp_path):
    frame = run(
        tmp_path,
        {"join": {"left": "orders", "right": "people", "on": "customer_id"}},
        {"select": ["order_id", "name"]},
        inputs={"orders": "orders", "people": "customers"},
    )

    # An inner join keeps the left order; order 4 has no customer.
    assert frame.to_dict("list") == {
        "order_id": [1, 2, 3],
        "name": ["Ada", "Grace", "Ada"],
    }


def test_an_operation_without_options_is_just_its_name(tmp_path):
    frame = run(tmp_path, "drop_nulls")

    assert frame["order_id"].tolist() == [1, 2, 3]


def test_your_function_as_an_operation(tmp_path, monkeypatch):
    module = types.ModuleType("dagcraft_chain_helpers")
    module.tag = lambda data, label: data.assign(label=label)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)

    frame = run(
        tmp_path,
        {"python": {"callable": "dagcraft_chain_helpers:tag", "label": "web"}},
        {"select": ["label"]},
    )

    assert set(frame["label"]) == {"web"}


def test_your_own_registered_operation(tmp_path):
    @register_operation("dagcraft_test_top", main="n")
    def top(data, n, column="price"):
        return data.nlargest(n, column)

    frame = run(tmp_path, {"dagcraft_test_top": 2})

    assert frame["price"].tolist() == [50.0, 20.0]


def test_the_plan_lists_the_operations(tmp_path):
    plan = pipeline(tmp_path, "drop_nulls", {"filter": "price > 1"}).plan()

    assert plan[2].description == "transform: drop_nulls -> filter"


def test_each_operation_logs_what_it_did(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger="dagcraft"):
        run(tmp_path, "drop_nulls", {"select": ["order_id"]})

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        re.search(r"clean: drop_nulls: 4 rows x 4 columns -> 3 rows x 4 columns$", m)
        for m in messages
    )
    assert any(
        re.search(r"clean: select: .* -> 3 rows x 1 columns$", m) for m in messages
    )


def test_a_failure_names_the_operation(tmp_path):
    with pytest.raises(RunError) as exc_info:
        run(tmp_path, "drop_nulls", {"filter": "no_such_column > 1"})

    assert "failed at step 'clean': operation 2 (filter) failed:" in str(exc_info.value)


def test_a_failed_check_names_the_problems(tmp_path):
    with pytest.raises(RunError) as exc_info:
        run(tmp_path, {"check": {"not_null": ["customer_id"]}})

    assert "operation 1 (check) failed: customer_id has 1 missing values" in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    ("operations", "message"),
    [
        (["fliter"], "operation 1 (fliter): Unknown operation: 'fliter'"),
        (
            [{"select": {"colums": ["a"]}}],
            "operation 1 (select): unknown option 'colums'; it takes columns.",
        ),
        ([{"sort": {"ascending": False}}], "operation 1 (sort): needs 'by'."),
        (
            [{"join": {"right": "products", "on": "id"}}],
            "operation 1 (join): right: 'products' isn't one of this step's "
            "inputs (data).",
        ),
        (
            ["drop_nulls", {"join": {"left": "data", "right": "data", "on": "x"}}],
            "operation 2 (join): only the first operation can set left; after "
            "that, the left side is the result so far.",
        ),
        (
            [{"join": "customers"}],
            "operation 1 (join): takes options as a mapping",
        ),
        (
            [{"filter": "price > 1", "select": ["a"]}],
            "Operation 1 should be one operation",
        ),
        (
            [{"python": "dagcraft_no_such_module:f"}],
            "operation 1 (python): Could not import module 'dagcraft_no_such_module'",
        ),
    ],
)
def test_operations_are_checked_when_the_pipeline_loads(tmp_path, operations, message):
    with pytest.raises(ConfigError) as exc_info:
        pipeline(tmp_path, *operations)

    assert message in str(exc_info.value)


def test_a_transform_needs_somewhere_to_start(tmp_path):
    with pytest.raises(ConfigError, match="starts from its 'data' input, or from"):
        pipeline(tmp_path, "drop_nulls", inputs={"orders": "orders"})


def test_every_input_must_be_used(tmp_path):
    with pytest.raises(ConfigError, match="No operation uses the input 'customers'"):
        pipeline(
            tmp_path,
            "drop_nulls",
            inputs={"data": "orders", "customers": "customers"},
        )


def test_the_old_form_points_to_operations(tmp_path):
    with pytest.raises(ConfigError, match="instead of 'operation:' and 'args:'"):
        Pipeline.from_dict(
            {
                "pipeline": {"name": "old"},
                "steps": [
                    {"id": "orders", "type": "read", "path": "orders.csv"},
                    {
                        "id": "clean",
                        "type": "transform",
                        "operation": "drop_nulls",
                        "inputs": {"data": "orders"},
                    },
                ],
            },
            base_dir=tmp_path,
        )
