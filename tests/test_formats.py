import json
import sys
import types

import pandas as pd
import pytest
import yaml

from dagcraft import ConfigError, Pipeline, RunError


def run(tmp_path, *steps):
    return Pipeline.from_dict(
        {"pipeline": {"name": "test"}, "steps": list(steps)},
        base_dir=tmp_path,
    ).run()


def read(path, step_id="data", **fields):
    return {"id": step_id, "type": "read", "path": path, **fields}


def write(path, upstream="data", **fields):
    return {
        "id": f"save_{path}",
        "type": "write",
        "path": path,
        "inputs": {"data": upstream},
        **fields,
    }


def flatten(upstream="data", step_id="table", **args):
    return {
        "id": step_id,
        "type": "transform",
        "inputs": {"data": upstream},
        "operations": [{"flatten": args} if args else "flatten"],
    }


EVENTS = {
    "batch": "b1",
    "source": {"system": "app"},
    "events": [
        {"id": 1, "user": {"id": "u1", "country": "GB"}},
        {"id": 2, "user": {"id": "u2", "country": "PL"}},
    ],
}


@pytest.fixture
def helpers(monkeypatch):
    """
    A module of your own functions, as a python step would call.
    """
    module = types.ModuleType("dagcraft_format_helpers")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def test_json_is_read_as_python_data(tmp_path):
    (tmp_path / "batch.json").write_text(json.dumps(EVENTS))

    assert run(tmp_path, read("batch.json")).output("data") == EVENTS


def test_your_function_gets_the_document_and_can_write_one(tmp_path, helpers):
    (tmp_path / "batch.json").write_text(json.dumps(EVENTS))

    def countries(data):
        return {
            "batch": data["batch"],
            "countries": [e["user"]["country"] for e in data["events"]],
        }

    helpers.countries = countries

    run(
        tmp_path,
        read("batch.json"),
        {
            "id": "summary",
            "type": "python",
            "callable": "dagcraft_format_helpers:countries",
            "inputs": {"data": "data"},
        },
        write("summary.json", upstream="summary", args={"indent": 2}),
        write("summary.yaml", upstream="summary"),
    )

    expected = {"batch": "b1", "countries": ["GB", "PL"]}
    assert json.loads((tmp_path / "summary.json").read_text()) == expected
    assert (tmp_path / "summary.json").read_text().startswith('{\n  "batch"')
    assert yaml.safe_load((tmp_path / "summary.yaml").read_text()) == expected


def test_flatten_turns_documents_into_a_table(tmp_path):
    (tmp_path / "batch.json").write_text(json.dumps(EVENTS))

    frame = run(
        tmp_path,
        read("batch.json"),
        flatten(record_path="events", meta=["batch", ["source", "system"]]),
    ).output("table")

    assert frame.columns.tolist() == [
        "id",
        "user.id",
        "user.country",
        "batch",
        "source.system",
    ]
    assert frame["batch"].tolist() == ["b1", "b1"]


def test_flatten_args_on_a_read_point_to_the_operation(tmp_path):
    with pytest.raises(ConfigError) as exc_info:
        run(tmp_path, read("batch.json", args={"record_path": "events"}))

    assert "record_path turn documents into a table" in str(exc_info.value)
    assert "flatten operation" in str(exc_info.value)


def test_json_lines_are_read_as_a_list_of_records(tmp_path):
    lines = [json.dumps(record) for record in EVENTS["events"]]
    (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n\n")

    assert run(tmp_path, read("events.jsonl")).output("data") == EVENTS["events"]


def test_yaml_is_read_as_python_data_with_yaml_1_2_booleans(tmp_path):
    (tmp_path / "countries.yml").write_text(
        "- {code: NO, name: Norway, eu: false}\n- {code: PL, name: Poland, eu: true}\n"
    )

    assert run(tmp_path, read("countries.yml")).output("data") == [
        {"code": "NO", "name": "Norway", "eu": False},
        {"code": "PL", "name": "Poland", "eu": True},
    ]


def test_yaml_reads_take_no_args(tmp_path):
    with pytest.raises(ConfigError, match="Reading YAML takes no args"):
        run(tmp_path, read("countries.yml", args={"encoding": "utf-8"}))


@pytest.mark.parametrize("path", ["out.json", "out.jsonl", "out.yaml", "out.ndjson"])
def test_tables_are_written_as_records(tmp_path, path):
    pd.DataFrame(
        {
            "name": ["Zoë", "Ada"],
            "score": [1.5, None],
            "when": pd.to_datetime(["2026-10-01", "2026-10-02"]),
        }
    ).to_parquet(tmp_path / "in.parquet")

    run(tmp_path, read("in.parquet"), write(path))
    back = run(tmp_path, read(path)).output("data")

    assert back == [
        {"name": "Zoë", "score": 1.5, "when": "2026-10-01T00:00:00.000"},
        {"name": "Ada", "score": None, "when": "2026-10-02T00:00:00.000"},
    ]


def test_dates_in_documents_are_written_as_iso_text(tmp_path, helpers):
    helpers.document = lambda: {"day": pd.Timestamp("2026-10-03").date()}

    run(
        tmp_path,
        {
            "id": "data",
            "type": "python",
            "callable": "dagcraft_format_helpers:document",
        },
        write("out.json"),
    )

    assert json.loads((tmp_path / "out.json").read_text()) == {"day": "2026-10-03"}


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("out.csv", "A csv file"),
        ("out.parquet", "A parquet file"),
        ("out.xlsx", "Excel"),
    ],
)
def test_table_formats_need_a_table(tmp_path, path, target):
    (tmp_path / "batch.json").write_text(json.dumps(EVENTS))

    with pytest.raises(RunError) as exc_info:
        run(tmp_path, read("batch.json"), write(path))

    assert f"{target} needs a table (a DataFrame), not an object with 3 keys" in str(
        exc_info.value
    )
