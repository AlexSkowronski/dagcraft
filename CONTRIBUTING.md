# Contributing to dagcraft

## Setting up

```bash
uv sync                    # the package, dev tools and every optional extra
uv run pre-commit install  # lint, format and type checks on commit; tests on push
uv run pytest
```

Type checking uses Pyright, the checker behind VS Code's Pylance, so the
editor and the hooks report the same problems. CI runs the same checks,
builds the package and the docs, and runs the tests on Python 3.11 to 3.14
on Linux and on Windows.

## How the code is organised

One concern per module, organised by job:

```
src/dagcraft/
  config/        what a pipeline file can say: pydantic models only
  core/          compiling and running: graph, scheduler, step runner, ...
  connections/   where data lives and signing in: files/ and sql/
  readers/       what a read step fetches, per kind of connection
  writers/       what a write step puts, per kind of connection
  formats/       how a file becomes data, one format per module
  steps/         read, write, transform, python
  operations/    built-in transform operations
  cli/           the dagcraft command: arguments, main, report
  schema/        JSON Schemas for editor autocomplete
  data.py        describing step outputs; requiring a table
  logs.py        run and step context for log messages
```

Docstrings open and close on their own lines, with the summary on the
second line; ruff checks it.

`schemas/` holds the JSON Schemas editors use for autocomplete, generated
from the config models and operations. After changing either, regenerate
them (a test fails until you do):

```bash
uv run dagcraft --schema schemas
```

## Documentation

The guide at <https://alexskowronski.github.io/dagcraft/> is built from
`docs/` with MkDocs (Material theme) and published from `main` by the Docs
workflow. Preview it while you edit:

```bash
uv run --group docs mkdocs serve    # http://127.0.0.1:8000
```

`README.md` is the PyPI page: keep it short and link into the guide with
full URLs, since PyPI doesn't resolve relative links. It only changes on
PyPI with a release.

## Releasing

1. Set `version` in `pyproject.toml`, and move the changes under
   `[Unreleased]` in `CHANGELOG.md` into a section for that version with
   today's date.
2. Commit, then tag and push the tag:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

The release workflow checks that the tag, `pyproject.toml` and the changelog
agree, runs the tests, publishes to PyPI with trusted publishing, and
creates a GitHub release with the changelog's notes.

To try a release before it's final, publish a pre-release the same way with
a version such as `0.1.0rc1`. It uses the notes of the release it leads up
to (`0.1.0`) unless the changelog has a section of its own, and GitHub marks
it as a pre-release. Install it by naming it:

```bash
pip install "dagcraft-pipelines[all]==0.1.0rc1"
```

PyPI trusts the release workflow through a trusted publisher (project
`dagcraft-pipelines`, owner `AlexSkowronski`, repository `dagcraft`, workflow
`release.yml`, environment `pypi`), so no API token is stored anywhere.
