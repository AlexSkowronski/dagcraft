import pytest

from dagcraft import Pipeline
from dagcraft.exceptions import ConfigError


def make_config(*steps):
    return {
        "pipeline": {"name": "test"},
        "steps": list(steps),
    }


def test_valid_config_parses():
    pipeline = Pipeline.from_dict(
        make_config(
            {"id": "src", "type": "read", "connector": "csv"},
        )
    )

    assert pipeline.config.pipeline.name == "test"
    assert pipeline.config.steps[0].id == "src"


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (
            {"id": "a", "type": "read"},
            "Read step 'a' requires a connector.",
        ),
        (
            {
                "id": "a",
                "type": "read",
                "connector": "csv",
                "inputs": {"data": "b"},
            },
            "Read step 'a' cannot have upstream inputs.",
        ),
        (
            {"id": "a", "type": "transform"},
            "Transform step 'a' requires an operation.",
        ),
        (
            {"id": "a", "type": "python"},
            "Python step 'a' requires a callable.",
        ),
        (
            {"id": "a", "type": "write", "inputs": {"data": "b"}},
            "Write step 'a' requires a connector.",
        ),
        (
            {"id": "a", "type": "write", "connector": "csv"},
            "Write step 'a' requires at least one input.",
        ),
        (
            {
                "id": "a",
                "type": "transform",
                "operation": "filter",
                "inputs": {"data": "b"},
                "args": {"data": 1},
            },
            "Step 'a' contains names in both inputs and args: data",
        ),
    ],
)
def test_step_validation_messages(step, message):
    with pytest.raises(ConfigError) as exc_info:
        Pipeline.from_dict(make_config(step))

    assert message in str(exc_info.value)


def test_duplicate_step_ids_rejected():
    step = {"id": "a", "type": "read", "connector": "csv"}

    with pytest.raises(
        ConfigError,
        match="Duplicate step ids found: a",
    ):
        Pipeline.from_dict(make_config(step, step))


def test_unknown_fields_rejected():
    with pytest.raises(ConfigError, match="extra_forbidden"):
        Pipeline.from_dict(
            make_config(
                {
                    "id": "a",
                    "type": "read",
                    "connector": "csv",
                    "unexpected": True,
                },
            )
        )


def test_from_yaml_missing_file(tmp_path):
    with pytest.raises(
        ConfigError,
        match="Could not read pipeline file",
    ):
        Pipeline.from_yaml(tmp_path / "missing.yaml")


def test_from_yaml_invalid_yaml(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("steps: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid YAML"):
        Pipeline.from_yaml(path)


def test_from_yaml_empty_file(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigError):
        Pipeline.from_yaml(path)
