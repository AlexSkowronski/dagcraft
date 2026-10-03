import pandas as pd
import pytest

from dagcraft.data import describe_data, require_table
from dagcraft.exceptions import ExecutionError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pd.DataFrame({"a": range(1234), "b": 0}), "1,234 rows x 2 columns"),
        ({"North": pd.DataFrame(), "South": pd.DataFrame()}, "2 tables (North, South)"),
        ({"batch": "b1", "events": []}, "an object with 2 keys"),
        ([{"id": 1}] * 1500, "a list of 1,500 items"),
        (None, "no output"),
        ({"only": 1}, "an object with 1 key"),
        (42, "int"),
    ],
)
def test_describe_data(value, expected):
    assert describe_data(value) == expected


def test_require_table_passes_tables_through():
    frame = pd.DataFrame({"a": [1]})

    assert require_table(frame, "A SQL table") is frame


def test_require_table_says_what_it_got():
    with pytest.raises(ExecutionError) as exc_info:
        require_table([{"id": 1}], "A SQL table")

    assert str(exc_info.value) == (
        "A SQL table needs a table (a DataFrame), not a list of 1 item. Turn "
        "documents into one with the flatten operation or a python step."
    )
