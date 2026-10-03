"""
Release metadata stays consistent: version, changelog and release notes.
"""

import importlib.util
import tomllib
from pathlib import Path

import dagcraft

ROOT = Path(__file__).resolve().parents[1]


def load_release_notes():
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "scripts" / "release_notes.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_version():
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def test_installed_version_matches_pyproject():
    assert dagcraft.__version__ == project_version()


def test_changelog_has_notes_for_the_current_version():
    notes = load_release_notes()

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert notes.notes_for(changelog, project_version())


def test_section_stops_at_the_next_heading_or_links():
    notes = load_release_notes()
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n"
        "## [0.2.0] - 2026-11-01\n\n- New thing.\n\n"
        "## [0.1.0] - 2026-10-02\n\n- First.\n\n"
        "[0.2.0]: https://example.com/0.2.0\n"
    )

    assert notes.section(changelog, "0.2.0") == "- New thing."
    assert notes.section(changelog, "0.1.0") == "- First."
    assert notes.section(changelog, "Unreleased") is None
    assert notes.section(changelog, "9.9.9") is None


def test_pre_releases_use_their_release_notes_unless_they_have_their_own():
    notes = load_release_notes()
    changelog = (
        "## [0.2.0rc2] - 2026-10-20\n\n- Fix for rc1.\n\n"
        "## [0.2.0] - Unreleased\n\n- New thing.\n"
    )

    assert notes.notes_for(changelog, "0.2.0rc1") == "- New thing."
    assert notes.notes_for(changelog, "0.2.0b1") == "- New thing."
    assert notes.notes_for(changelog, "0.2.0.dev3") == "- New thing."
    assert notes.notes_for(changelog, "0.2.0rc2") == "- Fix for rc1."
    # Only pre-releases fall back.
    assert notes.notes_for(changelog, "0.2.0.post1") is None
