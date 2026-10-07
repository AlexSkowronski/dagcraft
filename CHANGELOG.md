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
- `after:` on any step: wait for other steps without taking their output,
  such as reading a table once it's loaded.
- A self-checking pipeline in `config/checks/sql_server` proves writes,
  upserts, partitioned reads and query parameters against your database.
- Step types: `read`, `write`, `transform` and `python` (any importable
  function, including modules in the folder you run from, also with the
  `dagcraft` command).
- Transforms are a list of operations applied in order (`operations:`), so
  one step holds a whole stage of cleaning. Operations: `filter`,
  `drop_nulls`, `dedupe`, `sort`, `select`, `drop`, `rename`, `cast`,
  `derive`, `fill_nulls`, `join` (`left` and `right` inputs), `aggregate`,
  `flatten`, `check` (data quality checks that fail or warn) and `python`
  (your own function). Options are checked when the pipeline loads; each
  operation logs its effect at DEBUG and is named when it fails. (In
  0.1.0rc2 and before, a transform was one `operation:` with `args:`.)
- Validation when a pipeline loads: every field of every step and
  connection, the operations, functions, connections, formats and query
  files it names, and the graph, with one-line error messages.
- Relative paths in a pipeline file (`env_file`, `query_file`, local roots,
  SQLite files) are resolved from the folder you run from, like the path
  passed to `Pipeline.from_yaml`, or from its `base_dir`. (In 0.1.0rc1 they
  were relative to the pipeline file.)
- Params, `${params.NAME}` and `${env:NAME}` references, overridable from
  Python.
- Secrets written as `${env:NAME}` are held as secrets, never shown in logs;
  `env_file` loads a `.env` file first.
- Shared connections: pipelines `include` files of connections, so a
  project defines each connection once; a pipeline can override one.
- Autocomplete for pipeline files in VS Code: JSON Schemas built from the
  steps, connections and operations (`dagcraft --schema DIR`), published
  with the guide.
- Connections: `local`, `azure_blob` (including ADLS Gen2), `sharepoint`
  (through Microsoft Graph), `sql` (any SQLAlchemy URL) and `azure_sql`
  (Entra ID token per connection, `fast_executemany`). Signing in with
  `az login`, managed identity, a service principal or a connection string.
- Formats: CSV, Parquet and Excel (several sheets in, one sheet per input
  out) as tables; JSON, JSON Lines and YAML as plain Python data (dicts and
  lists) for your own python steps, with a `flatten` operation to turn
  documents into a table. (In 0.1.0rc1, documents were read as tables.)
- Reading many files at once, up to `parallel` at a time: by wildcard, or
  the files another step lists (`inputs: {paths: ...}`, with `path_column`),
  including full Azure Blob URLs. Optionally recording each row's file.
- A read that finds nothing (no rows, no files) is never quiet: it fails by
  default, or with `if_empty: stop` skips the steps that need it and the
  run succeeds with a warning; `continue` carries on with the empty result.
- SQL reads from inline queries, `.sql` files or whole tables, with bound
  parameters; transactional writes with `fail`, `append`, `delete_rows`,
  `replace` or `upsert` (replace the rows whose `keys` match, add the
  rest: safe to re-run).
- Partitioned SQL reads: split a large read into ranges of a whole-number
  column, read in parallel on separate connections (`partition`).
- Retries for any step, with a growing delay (`retries`, `retry_delay`).
- Local files are written under a temporary name and then moved into place,
  so a failed write leaves the previous file intact.
- Logging: each step logs when it starts, what it did (rows and columns)
  and how long it took, with progress for long reads and detail at DEBUG.
  Every message and record names the pipeline, run ID and step.
  `configure_logging()` for scripts; `Timer` for timing your own code.
- Run IDs, random or supplied (`run(run_id=...)`, `--run-id`).
- `run(keep_outputs=False)` drops each step's output once nothing else
  needs it, to save memory; the command line always runs this way.
- Independent steps can run in parallel (`max_workers` in the pipeline
  file, `run(max_workers=...)`, `--max-workers`).
- When a step fails, only the steps that depend on it are skipped;
  `RunError` names every failure. `fail_fast` stops at the first. Every
  error is a `PipelineError`.
- The `dagcraft pipeline.yaml` command (or `python -m dagcraft`) with
  `--dry-run`, `--check-connections`, `--fail-fast`, `--max-workers`,
  `--run-id`, `--verbose` and `--version`, exiting 0, 1 (failed) or 2
  (invalid); `Pipeline.plan()` and `Pipeline.check_connections()` from
  Python.
- Extension points for step types, operations, connections, readers,
  writers and formats.
- Optional extras: `excel`, `sql`, `azure` and `all`.
- Example pipelines in `config/examples` with sample data in `data/sample`.
- A guide at https://alexskowronski.github.io/dagcraft/: getting started,
  every connection, format and step, recipes, and extending dagcraft.

[Unreleased]: https://github.com/AlexSkowronski/dagcraft/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlexSkowronski/dagcraft/releases/tag/v0.1.0
