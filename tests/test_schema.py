import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
from jsonschema.exceptions import best_match

from dagcraft import register_operation
from dagcraft.cli import main
from dagcraft.schema import connections_schema, pipeline_schema
from dagcraft.yaml_loader import load_yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "config" / "examples").glob("*.yaml"))


@pytest.fixture(scope="module")
def validator():
    return jsonschema.Draft7Validator(pipeline_schema())


def problem(validator, text):
    """
    Where the schema finds the main problem in a pipeline, and what it is.
    """
    error = best_match(validator.iter_errors(load_yaml(text)))
    return None if error is None else (list(error.absolute_path), error.message)


def transform(operations):
    return (
        "pipeline: {name: x}\n"
        "steps:\n"
        "  - {id: b, type: read, path: in.csv}\n"
        "  - id: a\n"
        "    type: transform\n"
        "    inputs: {data: b, people: b}\n"
        f"    operations: {operations}\n"
    )


def test_the_schemas_are_valid_json_schemas():
    jsonschema.Draft7Validator.check_schema(pipeline_schema())
    jsonschema.Draft7Validator.check_schema(connections_schema())


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: path.stem)
def test_every_example_matches_the_schema(validator, path):
    assert problem(validator, path.read_text(encoding="utf-8")) is None


def test_shared_connection_files_have_their_own_schema():
    shared = load_yaml(
        "connections:\n  lake: {type: azure_blob, account: acct, container: raw}\n"
    )
    validator = jsonschema.Draft7Validator(connections_schema())

    assert not list(validator.iter_errors(shared))
    assert list(validator.iter_errors({"connections": {}, "params": {"a": 1}}))


@pytest.mark.parametrize(
    ("operations", "path", "message"),
    [
        ("[{fliter: x > 1}]", ["steps", 1, "operations", 0], "'fliter' was unexpected"),
        (
            "[{join: {lft: b, right: people, on: id}}]",
            ["steps", 1, "operations", 0, "join"],
            "'lft' was unexpected",
        ),
        (
            "[{dedupe: {keep: middle}}]",
            ["steps", 1, "operations", 0, "dedupe", "keep"],
            "'middle' is not one of ['first', 'last']",
        ),
    ],
)
def test_mistakes_in_operations_are_found(validator, operations, path, message):
    found = problem(validator, transform(operations))

    assert found is not None
    assert found[0] == path
    assert message in found[1]


def test_mistakes_in_steps_and_connections_are_found(validator):
    assert problem(
        validator,
        "pipeline: {name: x}\nsteps:\n  - {id: a, type: read, pth: in.csv}\n",
    ) == (["steps", 0], "Additional properties are not allowed ('pth' was unexpected)")

    assert problem(
        validator,
        "pipeline: {name: x}\n"
        "connections:\n  lake: {type: azure_blob, acount: acct, container: raw}\n"
        "steps: []\n",
    ) == (
        ["connections", "lake"],
        "Additional properties are not allowed ('acount' was unexpected)",
    )


def test_references_can_stand_in_for_any_value(validator):
    text = (
        "pipeline: {name: x, max_workers: '${env:WORKERS}'}\n"
        "steps:\n"
        "  - {id: b, type: read, path: in.csv, retries: '${params.retries}'}\n"
        "  - id: a\n"
        "    type: transform\n"
        "    inputs: {data: b}\n"
        "    operations: [{select: '${params.columns}'}, {sort: {by: x, "
        "ascending: '${params.ascending}'}}]\n"
    )

    assert problem(validator, text) is None


def test_your_own_operations_are_in_the_schema():
    @register_operation("dagcraft_schema_test_top", main="n")
    def top(data, n: int, column: str = "price"):
        """
        The ``n`` rows with the largest ``column``.
        """
        return data.nlargest(n, column)

    validator = jsonschema.Draft7Validator(pipeline_schema())
    entry = pipeline_schema()["properties"]["steps"]["items"]["allOf"]

    assert problem(validator, transform("[{dagcraft_schema_test_top: 5}]")) is None
    assert problem(validator, transform("[{dagcraft_schema_test_top: lots}]"))
    assert "The `n` rows with the largest `column`." in json.dumps(entry)


def test_the_committed_schemas_are_up_to_date(tmp_path):
    # A fresh process, so operations other tests register aren't included.
    subprocess.run(  # noqa: S603 - our own command, into a test folder
        [sys.executable, "-m", "dagcraft", "--schema", str(tmp_path)],
        check=True,
        capture_output=True,
    )

    for name in ("pipeline.json", "connections.json"):
        fresh = (tmp_path / name).read_text(encoding="utf-8")
        committed = (ROOT / "schemas" / name).read_text(encoding="utf-8")
        assert committed == fresh, (
            f"schemas/{name} is out of date: run 'uv run dagcraft --schema schemas'"
        )


def test_the_command_writes_the_schemas(tmp_path):
    assert main(["--schema", str(tmp_path / "schemas")]) == 0

    written = json.loads((tmp_path / "schemas" / "pipeline.json").read_text("utf-8"))
    assert written["title"] == "dagcraft pipeline"
    assert (tmp_path / "schemas" / "connections.json").exists()
