"""
Print the CHANGELOG.md section for a version, for its release notes.

    python scripts/release_notes.py 0.1.0

Exits with an error if the changelog has no section for that version, so a
release can't go out without notes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


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
    notes = section(CHANGELOG.read_text(encoding="utf-8"), version)

    if notes is None:
        print(f"CHANGELOG.md has no notes for {version}.", file=sys.stderr)
        return 1

    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
