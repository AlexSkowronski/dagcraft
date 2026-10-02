import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline, extras


def run(tmp_path, *steps):
    return Pipeline.from_dict(
        {"pipeline": {"name": "test"}, "steps": list(steps)},
        base_dir=tmp_path,
    ).run()


@pytest.fixture
def workbook(tmp_path):
    with pd.ExcelWriter(tmp_path / "sales.xlsx") as writer:
        pd.DataFrame({"month": [1, 2], "revenue": [10, 20]}).to_excel(
            writer, sheet_name="North", index=False
        )
        pd.DataFrame({"month": [1], "revenue": [5]}).to_excel(
            writer, sheet_name="South", index=False
        )
        pd.DataFrame({"region": ["North"], "target": [25]}).to_excel(
            writer, sheet_name="Targets", index=False
        )


@pytest.mark.usefixtures("workbook")
def test_reads_the_first_sheet_by_default(tmp_path):
    frame = run(tmp_path, {"id": "s", "type": "read", "path": "sales.xlsx"})

    assert frame.artifact("s").to_dict("list") == {"month": [1, 2], "revenue": [10, 20]}


@pytest.mark.usefixtures("workbook")
def test_reads_a_named_sheet(tmp_path):
    frame = run(
        tmp_path,
        {
            "id": "s",
            "type": "read",
            "path": "sales.xlsx",
            "args": {"sheet_name": "Targets"},
        },
    ).artifact("s")

    assert frame.to_dict("list") == {"region": ["North"], "target": [25]}


@pytest.mark.usefixtures("workbook")
def test_reads_several_sheets_into_one_table(tmp_path):
    frame = run(
        tmp_path,
        {
            "id": "s",
            "type": "read",
            "path": "sales.xlsx",
            "args": {"sheet_name": ["North", "South"], "sheet_column": "region"},
        },
    ).artifact("s")

    assert frame.to_dict("list") == {
        "month": [1, 2, 1],
        "revenue": [10, 20, 5],
        "region": ["North", "North", "South"],
    }


@pytest.mark.usefixtures("workbook")
def test_sheet_name_null_reads_every_sheet(tmp_path):
    frame = run(
        tmp_path,
        {"id": "s", "type": "read", "path": "sales.xlsx", "args": {"sheet_name": None}},
    ).artifact("s")

    assert frame["sheet"].unique().tolist() == ["North", "South", "Targets"]


@pytest.mark.usefixtures("workbook")
def test_several_inputs_become_sheets(tmp_path):
    run(
        tmp_path,
        {
            "id": "north",
            "type": "read",
            "path": "sales.xlsx",
            "args": {"sheet_name": "North"},
        },
        {
            "id": "targets",
            "type": "read",
            "path": "sales.xlsx",
            "args": {"sheet_name": "Targets"},
        },
        {
            "id": "report",
            "type": "write",
            "path": "out/report.xlsx",
            "inputs": {"Revenue": "north", "Goals": "targets"},
        },
    )

    sheets = pd.read_excel(tmp_path / "out" / "report.xlsx", sheet_name=None)
    assert list(sheets) == ["Revenue", "Goals"]
    assert sheets["Goals"].to_dict("list") == {"region": ["North"], "target": [25]}


def test_single_table_sheet_name(tmp_path):
    pd.DataFrame({"a": [1]}).to_csv(tmp_path / "in.csv", index=False)

    run(
        tmp_path,
        {"id": "data", "type": "read", "path": "in.csv"},
        {
            "id": "save",
            "type": "write",
            "path": "out.xlsx",
            "inputs": {"data": "data"},
            "args": {"sheet_name": "Data"},
        },
    )

    assert list(pd.read_excel(tmp_path / "out.xlsx", sheet_name=None)) == ["Data"]


def test_missing_openpyxl_is_a_config_error(tmp_path, monkeypatch):
    monkeypatch.setattr(extras, "module_available", lambda _module: False)

    with pytest.raises(ConfigError) as exc_info:
        Pipeline.from_dict(
            {
                "pipeline": {"name": "test"},
                "steps": [{"id": "s", "type": "read", "path": "sales.xlsx"}],
            },
            base_dir=tmp_path,
        )

    assert "Reading and writing .xlsx files needs the 'excel' extra" in str(
        exc_info.value
    )
