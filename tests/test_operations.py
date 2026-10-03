import logging

import pandas as pd
import pytest

from dagcraft.exceptions import ExecutionError
from dagcraft.operations import (
    aggregate,
    cast_columns,
    check,
    dedupe,
    derive_columns,
    drop_columns,
    drop_nulls,
    fill_nulls,
    filter_rows,
    join,
    rename_columns,
    select_columns,
    sort_rows,
)

SALES = pd.DataFrame(
    {
        "region": ["North", "South", "North", None],
        "revenue": [10, 20, 30, 40],
        "units": [1, 2, 3, 4],
    }
)


def test_filter_rows():
    assert filter_rows(SALES, "revenue > 15")["revenue"].tolist() == [20, 30, 40]


def test_drop_nulls():
    assert len(drop_nulls(SALES)) == 3
    assert len(drop_nulls(SALES, subset=["revenue"])) == 4


def test_dedupe():
    assert dedupe(SALES, subset=["region"])["revenue"].tolist() == [10, 20, 40]
    assert dedupe(SALES, subset=["region"], keep="last")["revenue"].tolist() == [
        20,
        30,
        40,
    ]


def test_sort_rows():
    assert sort_rows(SALES, "revenue", ascending=False)["revenue"].tolist() == [
        40,
        30,
        20,
        10,
    ]


def test_select_and_drop_columns():
    assert select_columns(SALES, ["units"]).columns.tolist() == ["units"]
    assert drop_columns(SALES, ["units"]).columns.tolist() == ["region", "revenue"]


def test_rename_columns():
    renamed = rename_columns(SALES, revenue="sales", **{"units sold": "n"})
    assert renamed.columns.tolist() == ["region", "sales", "units"]


def test_cast_columns():
    frame = pd.DataFrame({"n": ["1", None], "when": ["2026-10-01", "2026-10-02"]})

    cast = cast_columns(frame, n="int", when="datetime")

    assert str(cast["n"].dtype) == "Int64"
    assert cast["n"].isna().tolist() == [False, True]
    assert pd.api.types.is_datetime64_any_dtype(cast["when"])


def test_derive_columns_can_use_each_other():
    derived = derive_columns(SALES, price="revenue / units", double="price * 2")

    assert derived["price"].tolist() == [10.0, 10.0, 10.0, 10.0]
    assert derived["double"].tolist() == [20.0, 20.0, 20.0, 20.0]
    assert "price" not in SALES.columns


def test_fill_nulls():
    assert fill_nulls(SALES, region="Unknown")["region"].tolist() == [
        "North",
        "South",
        "North",
        "Unknown",
    ]


def test_join():
    targets = pd.DataFrame({"region": ["North"], "target": [35]})
    joined = join(SALES, targets, on="region", how="left")

    assert joined["target"].isna().tolist() == [False, True, False, True]
    assert joined["target"][0] == 35


def test_aggregate():
    totals = aggregate(SALES, by="region", columns={"revenue": "sum", "units": "max"})

    assert totals.to_dict("list") == {
        "region": ["North", "South"],
        "revenue": [40, 20],
        "units": [3, 2],
    }


def test_check_passes_good_data_through():
    assert check(SALES, columns=["region"], not_null=["revenue"], min_rows=1) is SALES


def test_check_reports_every_problem():
    with pytest.raises(ExecutionError) as exc_info:
        check(
            SALES,
            columns=["profit"],
            not_null=["region"],
            unique=["region"],
            accepted={"region": ["North"]},
            max_rows=3,
        )

    assert str(exc_info.value) == (
        "missing columns: profit; "
        "region has 1 missing values; "
        "2 rows share region with another row, such as region='North'; "
        "region has 1 values not in ['North'], such as 'South'; "
        "has 4 rows, more than 3"
    )


def test_check_can_warn_instead(caplog):
    with caplog.at_level(logging.WARNING, logger="dagcraft"):
        result = check(SALES, min_rows=10, warn=True)

    assert result is SALES
    assert "check found problems: has 4 rows, fewer than 10" in caplog.text
