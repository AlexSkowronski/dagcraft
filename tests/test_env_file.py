import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline

PIPELINE = """
pipeline:
  name: env
  env_file: {env_file}
connections:
  data:
    type: local
    root: ${{env:DAGCRAFT_TEST_ROOT}}
steps:
  - id: source
    type: read
    connection: data
    path: in.csv
"""


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    # Recorded as unset, so whatever the .env file sets is removed afterwards.
    monkeypatch.delenv("DAGCRAFT_TEST_ROOT", raising=False)


@pytest.fixture
def project(tmp_path):
    for folder in ("from_file", "from_environment"):
        (tmp_path / folder).mkdir()
        pd.DataFrame({"where": [folder]}).to_csv(tmp_path / folder / "in.csv")
    (tmp_path / ".env").write_text(
        "# comments and quotes work as usual\nDAGCRAFT_TEST_ROOT='from_file'\n",
        encoding="utf-8",
    )
    return tmp_path


def write_pipeline(project, env_file=".env"):
    """
    The pipeline goes in configs/, with the .env at the project's root.
    """
    (project / "configs").mkdir(exist_ok=True)
    path = project / "configs" / "pipeline.yaml"
    path.write_text(PIPELINE.format(env_file=env_file), encoding="utf-8")
    return path


def test_variables_come_from_the_env_file(project):
    result = Pipeline.from_yaml(write_pipeline(project)).run()

    assert result.output("source")["where"].tolist() == ["from_file"]


def test_the_real_environment_wins(project, monkeypatch):
    monkeypatch.setenv("DAGCRAFT_TEST_ROOT", "from_environment")

    result = Pipeline.from_yaml(write_pipeline(project)).run()

    assert result.output("source")["where"].tolist() == ["from_environment"]


def test_env_file_is_found_from_where_you_run(project, monkeypatch):
    write_pipeline(project)
    monkeypatch.chdir(project)

    result = Pipeline.from_yaml("configs/pipeline.yaml").run()

    assert result.output("source")["where"].tolist() == ["from_file"]


def test_missing_env_file_is_a_config_error(project):
    with pytest.raises(ConfigError, match="env_file not found"):
        Pipeline.from_yaml(write_pipeline(project, env_file="missing.env"))
