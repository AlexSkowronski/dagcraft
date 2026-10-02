from typing import ClassVar

import pandas as pd
import pytest

from dagcraft import BaseStep, Pipeline, StepConfig, register_step
from dagcraft.cli import main


@register_step("snapshot")
class SnapshotStep(BaseStep):
    """Records which step outputs are still held when it runs."""

    config_model = StepConfig
    seen: ClassVar[dict[str, list[str]]] = {}

    def execute(self, context, inputs):
        self.seen[self.config.id] = sorted(context.artifacts)
        return self.config.id


@pytest.fixture(autouse=True)
def clear_snapshots():
    SnapshotStep.seen.clear()


def make_pipeline(tmp_path):
    pd.DataFrame({"n": [1, 2]}).to_csv(tmp_path / "in.csv", index=False)
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "memory"},
            "steps": [
                {"id": "a", "type": "read", "path": "in.csv"},
                {
                    "id": "b",
                    "type": "transform",
                    "operation": "drop_nulls",
                    "inputs": {"data": "a"},
                },
                {"id": "c", "type": "snapshot", "inputs": {"data": "b"}},
                # Declared last, so "a" must be kept until now.
                {"id": "d", "type": "snapshot", "inputs": {"data": "a"}},
            ],
        },
        base_dir=tmp_path,
    )


def test_outputs_are_dropped_once_no_step_needs_them(tmp_path):
    result = make_pipeline(tmp_path).run(keep_artifacts=False)

    assert result.success
    assert SnapshotStep.seen == {
        # "a" is still needed by "d"; "b" is this step's input.
        "c": ["a", "b"],
        # "b" was dropped after "c"; "c" had no consumers.
        "d": ["a"],
    }
    assert result.artifacts == {}


def test_outputs_are_kept_by_default(tmp_path):
    result = make_pipeline(tmp_path).run()

    assert sorted(result.artifacts) == ["a", "b", "c", "d"]
    assert SnapshotStep.seen["d"] == ["a", "b", "c"]


def test_missing_output_explains_why(tmp_path):
    result = make_pipeline(tmp_path).run(keep_artifacts=False)

    with pytest.raises(KeyError, match="keep_artifacts=False"):
        result.artifact("a")


def test_cli_does_not_keep_outputs(tmp_path, monkeypatch):
    calls = []
    original_run = Pipeline.run

    def recording_run(self, *args, **kwargs):
        calls.append(kwargs)
        return original_run(self, *args, **kwargs)

    monkeypatch.setattr(Pipeline, "run", recording_run)
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        "pipeline: {name: cli}\nsteps:\n  - {id: a, type: snapshot}\n",
        encoding="utf-8",
    )

    main(["run", str(path)])

    assert calls[0]["keep_artifacts"] is False
