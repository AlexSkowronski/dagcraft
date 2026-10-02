import pandas as pd

from dagcraft.operations import (
    aggregate,
    drop_nulls,
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


def test_drop_nulls():
    assert len(drop_nulls(SALES)) == 3
    assert len(drop_nulls(SALES, subset=["revenue"])) == 4


def test_filter_rows():
    assert filter_rows(SALES, "revenue > 15")["revenue"].tolist() == [20, 30, 40]


def test_select_columns():
    assert select_columns(SALES, ["units"]).columns.tolist() == ["units"]


def test_rename_columns():
    renamed = rename_columns(SALES, {"revenue": "sales"})
    assert renamed.columns.tolist() == ["region", "sales", "units"]


def test_sort_rows():
    assert sort_rows(SALES, "revenue", ascending=False)["revenue"].tolist() == [
        40,
        30,
        20,
        10,
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
