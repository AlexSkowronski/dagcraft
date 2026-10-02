# Changelog

Notable changes to dagcraft. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - Unreleased

First release.

### Added

- Pipelines described in YAML and run from Python
  (`Pipeline.from_yaml(path).run()`) or the `dagcraft` command.
- Step types: `read`, `write`, `transform` (built-in or registered
  operations) and `python` (any importable function).
- Validation when a pipeline loads: every field of every step and
  connection, the operations, functions, connections, formats and query
  files it names, and the graph, with one-line error messages.
- Params, `${params.NAME}` and `${env:NAME}` references, overridable from
  Python and the command line.
- Connections: `local`, `azure_blob` (including ADLS Gen2), `sharepoint`
  (through Microsoft Graph), `sql` (any SQLAlchemy URL) and `azure_sql`
  (Entra ID token per connection, `fast_executemany`).
- Formats: CSV, Parquet, Excel (several sheets in, one sheet per input
  out), JSON, JSON Lines and YAML (nested objects flattened into columns).
- Reading many files at once with wildcard paths, optionally recording
  each row's source file.
- SQL reads from inline queries, `.sql` files or whole tables, with bound
  parameters; transactional writes with `fail`, `append`, `delete_rows` or
  `replace`.
- Partitioned SQL reads: split a large read into ranges of a whole-number
  column, read in parallel on separate connections (`partition`).
- Operations: `drop_nulls`, `filter`, `select`, `rename`, `sort`, `join`
  and `aggregate`.
- Retries for any step, with a growing delay (`retries`, `retry_delay`).
- Local files are written under a temporary name and then moved into place,
  so a failed write leaves the previous file intact.
- Run IDs on every log message and record, random or supplied
  (`run(run_id=...)`, `--run-id`).
- `run(keep_artifacts=False)` drops each step's output once nothing else
  needs it, to save memory; the command line always runs this way.
- Independent steps can run in parallel (`max_workers` in the pipeline
  file, `run(max_workers=...)`, `--max-workers`).
- When a step fails, only the steps that depend on it are skipped;
  `PipelineError` names every failure. `fail_fast` stops at the first.
- `dagcraft run` with `--dry-run`, `--check-connections`, `--param`,
  `--fail-fast` and `--version`; `Pipeline.plan()` and
  `Pipeline.check_connections()` from Python.
- Extension points for step types, operations, connections and formats.
- Optional extras: `excel`, `sql`, `azure` and `all`.
- Example pipelines in `config/examples` with sample data in `data/sample`.

[Unreleased]: https://github.com/AlexSkowronski/dagcraft/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlexSkowronski/dagcraft/releases/tag/v0.1.0
