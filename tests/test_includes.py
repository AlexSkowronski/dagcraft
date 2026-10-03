import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline

SHARED = """
connections:
  landing:
    type: local
    root: data/landing
  archive:
    type: local
    root: data/archive
"""


@pytest.fixture(autouse=True)
def project(tmp_path):
    """
    A project with shared connections at its root and pipelines in configs/.
    """
    for folder, value in [("landing", "from landing"), ("archive", "from archive")]:
        (tmp_path / "data" / folder).mkdir(parents=True)
        pd.DataFrame({"where": [value]}).to_csv(
            tmp_path / "data" / folder / "in.csv", index=False
        )
    (tmp_path / "configs").mkdir()
    (tmp_path / "connections.yaml").write_text(SHARED, encoding="utf-8")


def load(tmp_path, body):
    path = tmp_path / "configs" / "pipeline.yaml"
    path.write_text(body, encoding="utf-8")
    return Pipeline.from_yaml("configs/pipeline.yaml")


def test_pipelines_use_shared_connections(tmp_path):
    pipeline = load(
        tmp_path,
        """
pipeline: {name: shared}
include: [connections.yaml]
steps:
  - {id: source, type: read, connection: landing, path: in.csv}
""",
    )

    assert pipeline.run().output("source")["where"].tolist() == ["from landing"]
    # Shared connections the steps don't use are left alone.
    assert pipeline.connections_in_use() == ["landing"]


def test_a_pipeline_can_override_a_shared_connection(tmp_path):
    pipeline = load(
        tmp_path,
        """
pipeline: {name: shared}
include: [connections.yaml]
connections:
  landing: {type: local, root: data/archive}
steps:
  - {id: source, type: read, connection: landing, path: in.csv}
""",
    )

    assert pipeline.run().output("source")["where"].tolist() == ["from archive"]


def test_two_files_defining_a_connection_is_an_error(tmp_path):
    (tmp_path / "more.yaml").write_text(SHARED, encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load(
            tmp_path,
            "pipeline: {name: shared}\n"
            "include: [connections.yaml, more.yaml]\n"
            "steps: []\n",
        )

    assert "Connection 'landing' is defined in both connections.yaml and more.yaml" in (
        str(exc_info.value)
    )


def test_errors_name_the_file_a_connection_came_from(tmp_path):
    (tmp_path / "broken.yaml").write_text(
        "connections:\n  lake: {type: azure_blob, account: acct}\n", encoding="utf-8"
    )

    with pytest.raises(ConfigError) as exc_info:
        load(tmp_path, "pipeline: {name: shared}\ninclude: [broken.yaml]\nsteps: []\n")

    assert "Connection 'lake' (from broken.yaml): container: Field required" in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        (None, "Included file not found: shared.yaml"),
        ("connections: [oops", "Invalid YAML in included file shared.yaml"),
        (
            "params: {year: 2026}\nconnections: {}\n",
            "shared.yaml: An included file can only hold 'connections'; it has params.",
        ),
    ],
)
def test_included_files_are_checked(tmp_path, contents, message):
    if contents is not None:
        (tmp_path / "shared.yaml").write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load(tmp_path, "pipeline: {name: shared}\ninclude: [shared.yaml]\nsteps: []\n")

    assert message in str(exc_info.value)
