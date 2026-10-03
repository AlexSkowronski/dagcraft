"""
The ``dagcraft`` command line: ``dagcraft pipeline.yaml [--dry-run] ...``.

parser.py   the arguments
command.py  main(): load, check, run, exit code
report.py   what gets logged: the plan, connection checks, run summary
"""

from dagcraft.cli.command import ExitCode, main

__all__ = ["ExitCode", "main"]
