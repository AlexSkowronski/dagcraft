import json

import pandas as pd
import pytest

from dagcraft import Pipeline


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


EVENTS = {
    "batch": "b1",
    "source": {"system": "app"},
    "events": [
        {"id": 1, "user": {"id": "u1", "country": "GB"}},
        {"id": 2, "user": {"id": "u2", "country": "PL"}},
    ],
}


def test_json_list_of_records_is_flattened(tmp_path):
    (tmp_path / "events.json").write_text(json.dumps(EVENTS["events"]))

    frame = run(tmp_path, read("events.json")).artifact("data")

    assert frame.to_dict("list") == {
        "id": [1, 2],
        "user.id": ["u1", "u2"],
        "user.country": ["GB", "PL"],
    }


def test_json_records_inside_a_document(tmp_path):
    (tmp_path / "batch.json").write_text(json.dumps(EVENTS))

    frame = run(
        tmp_path,
        read(
            "batch.json",
            args={"record_path": "events", "meta": ["batch", ["source", "system"]]},
        ),
    ).artifact("data")

    assert frame.columns.tolist() == [
        "id",
        "user.id",
        "user.country",
        "batch",
        "source.system",
    ]
    assert frame["batch"].tolist() == ["b1", "b1"]


def test_json_lines(tmp_path):
    lines = [json.dumps(record) for record in EVENTS["events"]]
    (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n\n")

    frame = run(tmp_path, read("events.jsonl")).artifact("data")

    assert frame["user.country"].tolist() == ["GB", "PL"]


def test_yaml_reads_like_json_with_yaml_1_2_booleans(tmp_path):
    (tmp_path / "countries.yml").write_text(
        "- {code: NO, name: Norway, eu: false}\n- {code: PL, name: Poland, eu: true}\n"
    )

    frame = run(tmp_path, read("countries.yml")).artifact("data")

    assert frame.to_dict("list") == {
        "code": ["NO", "PL"],
        "name": ["Norway", "Poland"],
        "eu": [False, True],
    }


@pytest.mark.parametrize("path", ["out.json", "out.jsonl", "out.yaml", "out.ndjson"])
def test_round_trip(tmp_path, path):
    pd.DataFrame(
        {
            "name": ["Zoë", "Ada"],
            "score": [1.5, None],
            "when": pd.to_datetime(["2026-10-01", "2026-10-02"]),
        }
    ).to_parquet(tmp_path / "in.parquet")

    run(tmp_path, read("in.parquet"), write(path))
    back = run(tmp_path, read(path)).artifact("data")

    assert back["name"].tolist() == ["Zoë", "Ada"]
    assert back["score"].iloc[0] == 1.5
    assert pd.isna(back["score"].iloc[1])
    assert back["when"].tolist() == [
        "2026-10-01T00:00:00.000",
        "2026-10-02T00:00:00.000",
    ]


def test_json_is_written_as_records(tmp_path):
    pd.DataFrame({"a": [1, 2]}).to_csv(tmp_path / "in.csv", index=False)

    run(tmp_path, read("in.csv"), write("out.json"))

    assert json.loads((tmp_path / "out.json").read_text()) == [{"a": 1}, {"a": 2}]
