import logging
import threading

import pandas as pd
import pytest
import sqlalchemy as sa
from sqlalchemy import event

from dagcraft import ConfigError, Pipeline, RunError
from dagcraft.readers.sql.partitions import split_range


@pytest.fixture
def warehouse(tmp_path):
    """orders: order_id 1..200 plus 3 rows without an id."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")
    orders = pd.DataFrame(
        {
            "order_id": pd.array([*range(1, 201), None, None, None], dtype="Int64"),
            "amount": [float(n) for n in range(203)],
            "label": [f"order-{n}" for n in range(203)],
        }
    )
    orders.to_sql("orders", engine, index=False)
    pd.DataFrame({"order_id": pd.array([], dtype="Int64")}).to_sql(
        "empty", engine, index=False
    )
    engine.dispose()
    return tmp_path


@pytest.fixture
def statements():
    """Every SQL statement run, with the thread that ran it."""
    seen: list[tuple[str, str]] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        seen.append((statement, threading.current_thread().name))

    event.listen(sa.engine.Engine, "before_cursor_execute", record)
    yield seen
    event.remove(sa.engine.Engine, "before_cursor_execute", record)


def read(base_dir, **fields):
    return (
        Pipeline.from_dict(
            {
                "pipeline": {"name": "parts"},
                "connections": {"db": {"type": "sql", "url": "sqlite:///warehouse.db"}},
                "steps": [{"id": "data", "type": "read", "connection": "db", **fields}],
            },
            base_dir=base_dir,
        )
        .run()
        .output("data")
    )


def sorted_rows(frame):
    return frame.sort_values("label").reset_index(drop=True)


def test_partitioned_table_matches_a_plain_read(warehouse, statements):
    whole = read(warehouse, table="orders")
    statements.clear()

    parts = read(
        warehouse, table="orders", partition={"column": "order_id", "parts": 4}
    )

    pd.testing.assert_frame_equal(sorted_rows(parts), sorted_rows(whole))

    sql = [statement for statement, _ in statements]
    assert sum("MIN(" in s for s in sql) == 1
    assert sum("BETWEEN" in s for s in sql) == 4
    assert sum("IS NULL" in s for s in sql) == 1
    # The parts ran on the read's own worker threads.
    worker_threads = {thread for s, thread in statements if "BETWEEN" in s}
    assert all(thread.startswith("dagcraft-sql") for thread in worker_threads)


def test_part_logs_name_the_step(warehouse, caplog):
    with caplog.at_level(logging.DEBUG, logger="dagcraft"):
        read(warehouse, table="orders", partition={"column": "order_id", "parts": 4})

    messages = [record.getMessage() for record in caplog.records]
    assert any(m.endswith("data: reading in 5 parts at once") for m in messages)
    # Logged from the read's own worker threads, which still know the step.
    parts = [m for m in messages if "data: read part" in m]
    assert len(parts) == 5
    assert any(m.endswith("read part 5 of 5 (NULL): 3 rows x 3 columns") for m in parts)


def test_explicit_bounds_skip_the_min_max_query(warehouse, statements):
    frame = read(
        warehouse,
        table="orders",
        partition={"column": "order_id", "parts": 2, "lower": 1, "upper": 50},
    )

    assert not any("MIN(" in statement for statement, _ in statements)
    # Rows outside the bounds aren't read; rows without an id still are.
    assert frame["order_id"].dropna().tolist() == list(range(1, 51))
    assert frame["order_id"].isna().sum() == 3


def test_partitioned_query_with_placeholders(warehouse, statements):
    frame = read(
        warehouse,
        query=(
            "-- uses :partition_start and :partition_end\n"
            "SELECT order_id, amount FROM orders\n"
            "WHERE order_id BETWEEN :partition_start AND :partition_end\n"
            "  AND amount >= :minimum"
        ),
        params={"minimum": 100},
        partition={"parts": 3, "lower": 1, "upper": 200},
    )

    assert sorted(frame["order_id"]) == list(range(101, 201))
    assert sum("BETWEEN" in statement for statement, _ in statements) == 3


def test_partitioned_query_file(warehouse):
    (warehouse / "orders.sql").write_text(
        "WITH recent AS (SELECT * FROM orders WHERE order_id > 150)\n"
        "SELECT order_id FROM recent\n"
        "WHERE order_id BETWEEN :partition_start AND :partition_end\n",
        encoding="utf-8",
    )

    frame = read(
        warehouse,
        query_file="orders.sql",
        partition={"parts": 4, "lower": 1, "upper": 200},
    )

    assert sorted(frame["order_id"]) == list(range(151, 201))


def test_empty_table_is_read_whole(warehouse):
    frame = read(warehouse, table="empty", partition={"column": "order_id", "parts": 4})

    assert frame.empty
    assert frame.columns.tolist() == ["order_id"]


def test_column_must_hold_whole_numbers(warehouse):
    with pytest.raises(RunError, match="must hold whole numbers"):
        read(warehouse, table="orders", partition={"column": "label", "parts": 2})


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"table": "orders", "partition": {"column": "order_id", "parts": 1}},
            "parts: Input should be greater than or equal to 2",
        ),
        (
            {"table": "orders", "partition": {"parts": 2}},
            "Partitioning a table needs 'partition.column'.",
        ),
        (
            {"query": "SELECT 1", "partition": {"parts": 2}},
            "Partitioning a query needs 'partition.lower' and 'partition.upper'.",
        ),
        (
            {"query": "SELECT 1", "partition": {"parts": 2, "lower": 1, "upper": 9}},
            "A partitioned query must use :partition_start and :partition_end.",
        ),
        (
            {
                "query": "SELECT 1 WHERE 1 BETWEEN :partition_start AND :partition_end",
                "params": {"partition_start": 5},
                "partition": {"parts": 2, "lower": 1, "upper": 9},
            },
            "'params' can't set partition_start here.",
        ),
        (
            {
                "table": "orders",
                "partition": {"column": "id", "parts": 2, "lower": 9, "upper": 1},
            },
            "'lower' can't be greater than 'upper'.",
        ),
        (
            {
                "query": "SELECT 1",
                "partition": {"column": "id", "parts": 2, "lower": 1, "upper": 9},
            },
            "'partition.column' only applies to tables",
        ),
    ],
)
def test_partition_validation(warehouse, fields, message):
    with pytest.raises(ConfigError) as exc_info:
        read(warehouse, **fields)

    assert message in str(exc_info.value)


def test_dry_run_describes_the_partitioning(warehouse):
    pipeline = Pipeline.from_dict(
        {
            "pipeline": {"name": "parts"},
            "connections": {"db": {"type": "sql", "url": "sqlite:///warehouse.db"}},
            "steps": [
                {
                    "id": "data",
                    "type": "read",
                    "connection": "db",
                    "table": "orders",
                    "partition": {"column": "order_id", "parts": 8},
                }
            ],
        },
        base_dir=warehouse,
    )

    [step] = pipeline.plan()
    assert (
        step.description
        == "read table orders in 8 parallel parts by order_id from 'db'"
    )


@pytest.mark.parametrize(
    ("lower", "upper", "parts", "expected"),
    [
        (1, 10, 3, [(1, 4), (5, 7), (8, 10)]),
        (1, 3, 8, [(1, 1), (2, 2), (3, 3)]),
        (5, 5, 4, [(5, 5)]),
        (-4, 3, 2, [(-4, -1), (0, 3)]),
    ],
)
def test_split_range(lower, upper, parts, expected):
    assert split_range(lower, upper, parts) == expected
