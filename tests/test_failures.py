import logging

import pandas as pd
import pytest

from dagcraft import Pipeline, RunError, StepStatus
from dagcraft.cli import main


@pytest.fixture(autouse=True)
def numbers_csv(tmp_path):
    pd.DataFrame({"n": [1, 2, 3]}).to_csv(tmp_path / "numbers.csv", index=False)


def read(step_id):
    return {"id": step_id, "type": "read", "path": "numbers.csv"}


def keep(step_id, upstream, expression="n > 1"):
    return {
        "id": step_id,
        "type": "transform",
        "inputs": {"data": upstream},
        "operations": [{"filter": expression}],
    }


def broken(step_id, upstream):
    return keep(step_id, upstream, expression="no_such_column > 1")


def run(tmp_path, *steps, fail_fast=False):
    pipeline = Pipeline.from_dict(
        {"pipeline": {"name": "test"}, "steps": list(steps)},
        base_dir=tmp_path,
    )

    with pytest.raises(RunError) as exc_info:
        pipeline.run(fail_fast=fail_fast)

    return exc_info.value


def statuses(error):
    return {step_id: step.status for step_id, step in error.result.steps.items()}


def test_independent_steps_keep_running(tmp_path):
    error = run(
        tmp_path,
        read("source"),
        broken("bad", "source"),
        keep("after_bad", "bad"),
        keep("good", "source"),
        keep("after_good", "good"),
        read("unrelated"),
    )

    assert statuses(error) == {
        "source": StepStatus.SUCCESS,
        "bad": StepStatus.FAILED,
        "after_bad": StepStatus.SKIPPED,
        "good": StepStatus.SUCCESS,
        "after_good": StepStatus.SUCCESS,
        "unrelated": StepStatus.SUCCESS,
    }
    assert error.result.output("after_good")["n"].tolist() == [2, 3]


def test_skips_carry_down_the_graph(tmp_path):
    error = run(
        tmp_path,
        read("source"),
        broken("bad", "source"),
        keep("child", "bad"),
        keep("grandchild", "child"),
    )

    assert statuses(error)["child"] == StepStatus.SKIPPED
    assert statuses(error)["grandchild"] == StepStatus.SKIPPED


def test_step_with_one_failed_input_is_skipped(tmp_path):
    error = run(
        tmp_path,
        read("left"),
        read("right"),
        broken("bad", "right"),
        {
            "id": "joined",
            "type": "transform",
            "inputs": {"data": "left", "right": "bad"},
            "operations": [{"join": {"right": "right", "on": "n"}}],
        },
    )

    assert statuses(error)["joined"] == StepStatus.SKIPPED


def test_fail_fast_skips_everything_after_the_first_failure(tmp_path):
    error = run(
        tmp_path,
        read("source"),
        broken("bad", "source"),
        keep("good", "source"),
        read("unrelated"),
        fail_fast=True,
    )

    assert statuses(error) == {
        "source": StepStatus.SUCCESS,
        "bad": StepStatus.FAILED,
        "good": StepStatus.SKIPPED,
        "unrelated": StepStatus.SKIPPED,
    }


def test_error_names_every_failed_step(tmp_path):
    error = run(
        tmp_path,
        read("source"),
        broken("first", "source"),
        broken("second", "source"),
    )

    assert str(error).startswith("Pipeline 'test' failed at step 'first':")
    assert str(error).endswith("(also failed: second)")
    assert [step.id for step in error.result.failed_steps] == ["first", "second"]
    assert error.__cause__ is error.result.steps["first"].exception


def test_skips_are_logged_with_the_reason(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="dagcraft"):
        run(tmp_path, read("source"), broken("bad", "source"), keep("child", "bad"))

    assert "child: skipped: upstream step 'bad' did not succeed" in caplog.text


def test_cli_fail_fast(tmp_path, caplog):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        """
pipeline:
  name: cli
steps:
  - id: source
    type: read
    path: numbers.csv
  - id: bad
    type: transform
    inputs: {data: source}
    operations: [filter: "no_such_column > 1"]
  - id: unrelated
    type: read
    path: numbers.csv
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        assert main([str(path), "--fail-fast"]) == 1

    summary = [
        r.getMessage() for r in caplog.records if r.name == "dagcraft.cli.report"
    ]
    assert any(line.startswith("SKIPPED    unrelated") for line in summary)
