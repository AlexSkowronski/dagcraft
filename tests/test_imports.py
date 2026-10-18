"""
``imports`` brings in your modules, so what they register can be named.
"""

import sys

import pandas as pd
import pytest

from dagcraft import ConfigError, Pipeline
from dagcraft.cli import ExitCode, main


@pytest.fixture(autouse=True)
def isolated_imports(monkeypatch):
    """
    Undo changes to the import path and forget the test's modules afterwards.
    """
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in [name for name in sys.modules if name.startswith("dagcraft_imports_")]:
        del sys.modules[name]


def write_module(tmp_path, name, code):
    (tmp_path / f"{name}.py").write_text(code, encoding="utf-8")


def load(*imports, **pipeline):
    return Pipeline.from_dict(
        {
            "pipeline": {"name": "imports", "imports": list(imports), **pipeline},
            "steps": [{"id": "orders", "type": "read", "path": "orders.csv"}],
        }
    )


def test_the_command_can_use_operations_your_modules_register(tmp_path):
    write_module(
        tmp_path,
        "dagcraft_imports_cleaning",
        "from dagcraft import register_operation\n"
        "\n"
        "\n"
        "@register_operation('dagcraft_imports_shout', main='column')\n"
        "def shout(data, column):\n"
        "    return data.assign(**{column: data[column].str.upper()})\n",
    )
    pd.DataFrame({"name": ["ada", "alan"]}).to_csv(tmp_path / "names.csv", index=False)
    (tmp_path / "pipeline.yaml").write_text(
        """
pipeline:
  name: shouting
  imports: [dagcraft_imports_cleaning]
steps:
  - id: names
    type: read
    path: names.csv
  - id: loud
    type: transform
    inputs: {data: names}
    operations:
      - dagcraft_imports_shout: name
  - id: save
    type: write
    path: loud.csv
    inputs: {data: loud}
""",
        encoding="utf-8",
    )

    assert main(["pipeline.yaml"]) == ExitCode.SUCCESS

    assert pd.read_csv(tmp_path / "loud.csv")["name"].tolist() == ["ADA", "ALAN"]


def test_modules_are_imported_after_the_env_file_loads(tmp_path, monkeypatch):
    # Set, then unset, so it's recorded as unset and the .env file's value
    # is removed afterwards.
    monkeypatch.setenv("DAGCRAFT_IMPORTS_GREETING", "")
    monkeypatch.delenv("DAGCRAFT_IMPORTS_GREETING")
    (tmp_path / ".env").write_text(
        "DAGCRAFT_IMPORTS_GREETING=hello\n", encoding="utf-8"
    )
    write_module(
        tmp_path,
        "dagcraft_imports_settings",
        "import os\n\nGREETING = os.environ['DAGCRAFT_IMPORTS_GREETING']\n",
    )

    load("dagcraft_imports_settings", env_file=".env")

    assert sys.modules["dagcraft_imports_settings"].GREETING == "hello"


@pytest.mark.parametrize(
    "module",
    [
        "dagcraft_imports_missing",
        "dagcraft_imports_missing.cleaning",
        "dagcraft.no_such_module",
    ],
)
def test_a_module_that_isnt_there_says_so(module):
    with pytest.raises(ConfigError) as exc_info:
        load(module)

    assert str(exc_info.value) == (
        f"Could not import module '{module}': it isn't in the folder you run "
        "from or an installed package."
    )


def test_a_module_that_fails_to_import_says_why(tmp_path):
    write_module(
        tmp_path,
        "dagcraft_imports_broken",
        "import dagcraft_imports_missing_dependency\n",
    )

    with pytest.raises(ConfigError) as exc_info:
        load("dagcraft_imports_broken")

    assert str(exc_info.value) == (
        "Could not import module 'dagcraft_imports_broken': "
        "No module named 'dagcraft_imports_missing_dependency'"
    )


def test_a_module_that_takes_a_registered_name_says_so(tmp_path):
    write_module(
        tmp_path,
        "dagcraft_imports_clash",
        "from dagcraft import register_operation\n"
        "\n"
        "\n"
        "@register_operation('filter')\n"
        "def my_filter(data):\n"
        "    return data\n",
    )

    with pytest.raises(ConfigError) as exc_info:
        load("dagcraft_imports_clash")

    assert str(exc_info.value) == (
        "Could not import module 'dagcraft_imports_clash': The name 'filter' is "
        "already taken by another operation."
    )


def test_imports_are_module_names_not_files():
    with pytest.raises(ConfigError, match=r"'functions/cleaning\.py' isn't a module"):
        load("functions/cleaning.py")
