"""
Print the CHANGELOG.md section for a version, for its release notes.

    python scripts/release_notes.py 0.1.0

A pre-release (0.1.0rc1, 0.1.0b2, ...) uses its own section if there is one,
or else the section of the version it leads up to (0.1.0). Exits with an
error if there are no notes, so a release can't go out without them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
# A pre-release or dev version (0.1.0rc1, 0.2.0.dev3): its release, then the rest.
PRE_RELEASE = re.compile(r"^(?P<release>\d+(?:\.\d+)*)(?:a|b|rc|\.dev)\d+")


def section(changelog: str, version: str) -> str | None:
    """
    The text under ``## [version]``, up to the next section or link list.
    """
    pattern = (
        rf"^## \[{re.escape(version)}\][^\n]*\n"
        r"(.*?)"
        r"(?=^## |^\[[^\]]+\]: |\Z)"
    )
    match = re.search(pattern, changelog, re.DOTALL | re.MULTILINE)

    if match is None or not match.group(1).strip():
        return None
    return match.group(1).strip()


def notes_for(changelog: str, version: str) -> str | None:
    """
    The notes for ``version``, falling back to its release's for a pre-release.
    """
    notes = section(changelog, version)
    pre_release = PRE_RELEASE.match(version)

    if notes is None and pre_release is not None:
        return section(changelog, pre_release["release"])
    return notes


def main(argv: list[str]) -> int:
    """
    Print the notes for the version in ``argv``; exit 1 if there are none.
    """
    try:
        [_, version] = argv
    except ValueError:
        print("usage: release_notes.py VERSION", file=sys.stderr)
        return 2

    version = version.removeprefix("v")
    notes = notes_for(CHANGELOG.read_text(encoding="utf-8"), version)

    if notes is None:
        print(f"CHANGELOG.md has no notes for {version}.", file=sys.stderr)
        return 1

    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
