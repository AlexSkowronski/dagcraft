"""
The example pipelines in config/examples keep working.
"""

from pathlib import Path

import pandas as pd
import pytest

from dagcraft import Pipeline

EXAMPLES = Path(__file__).resolve().parents[1] / "config" / "examples"

# Examples that run on sample data, with a file each one writes.
LOCAL = {
    "basic": "basic/salaried.csv",
    "local_sales": "local_sales/orders_by_region.csv",
    "json_events": "json_events/purchases.parquet",
    "excel_reports": "excel_reports/regional_report.xlsx",
    "sql_reports": "sql_reports/reports.db",
}

# Examples that need Azure or SharePoint to run.
TEMPLATES = {"azure_blob_to_sql", "sharepoint_reports"}


def example_paths():
    return sorted(EXAMPLES.glob("*.yaml"))


def test_every_example_is_listed():
    assert {path.stem for path in example_paths()} == set(LOCAL) | TEMPLATES


@pytest.mark.parametrize("path", example_paths(), ids=lambda path: path.stem)
def test_example_loads_and_plans(path):
    assert Pipeline.from_yaml(path).plan()


@pytest.mark.parametrize(("name", "output"), LOCAL.items())
def test_local_example_runs(tmp_path, name, output):
    result = Pipeline.from_yaml(
        EXAMPLES / f"{name}.yaml",
        params={"output_dir": tmp_path.as_posix()},
    ).run()

    assert result.success
    assert (tmp_path / output).exists()


def test_excel_report_has_a_sheet_per_input(tmp_path):
    Pipeline.from_yaml(
        EXAMPLES / "excel_reports.yaml",
        params={"output_dir": tmp_path.as_posix()},
    ).run()

    sheets = pd.read_excel(
        tmp_path / "excel_reports" / "regional_report.xlsx", sheet_name=None
    )

    assert list(sheets) == ["Summary", "Monthly"]
    assert sorted(sheets["Summary"]["region"]) == ["East", "North", "South", "West"]
    assert "revenue_target" in sheets["Summary"]


def test_json_events_are_flattened_and_joined(tmp_path):
    Pipeline.from_yaml(
        EXAMPLES / "json_events.yaml",
        params={"output_dir": tmp_path.as_posix()},
    ).run()

    purchases = pd.read_parquet(tmp_path / "json_events" / "purchases.parquet")

    assert set(purchases["type"]) == {"purchase"}
    assert {
        "user_id",
        "region",
        "product_id",
        "name",
        "batch_id",
        "source_file",
    } <= set(purchases.columns)
    assert purchases["name"].notna().all()
