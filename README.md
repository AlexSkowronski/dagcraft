# dagcraft

[![CI](https://github.com/AlexSkowronski/dagcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/AlexSkowronski/dagcraft/actions/workflows/ci.yml)

Config-driven DAG pipelines for Python. Describe your pipeline's steps in
YAML: read data, transform it, write it somewhere. dagcraft validates the
whole file up front, works out the order to run steps in, and runs them.

```python
from dagcraft import Pipeline

result = Pipeline.from_yaml("pipelines/daily_sales.yaml").run()
```

> Early development (0.1). The config format may still change.

## Installation

```bash
pip install dagcraft-pipelines            # local files: CSV, Parquet, JSON, JSON Lines, YAML
pip install 'dagcraft-pipelines[excel]'   # + Excel workbooks
pip install 'dagcraft-pipelines[sql]'     # + SQL databases through SQLAlchemy
pip install 'dagcraft-pipelines[azure]'   # + Azure Blob Storage, Azure SQL and SharePoint
pip install 'dagcraft-pipelines[all]'     # everything
```

The package is called `dagcraft-pipelines` on PyPI; you import it and run it
as `dagcraft`.

The `azure_sql` connection also needs Microsoft's
[ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
installed on the machine.

## Quick start

`pipelines/daily_sales.yaml`:

```yaml
pipeline:
  name: daily_sales

connections:
  lake:
    type: azure_blob
    account: mystorageacct
    container: raw

steps:
  - id: orders
    type: read
    connection: lake
    path: orders/2026-10-02.parquet

  - id: customers
    type: read
    path: data/customers.csv          # uses the built-in "local" connection

  - id: enriched
    type: transform
    operation: join
    inputs:
      left: orders
      right: customers
    args:
      on: customer_id
      how: left

  - id: save
    type: write
    path: out/enriched.parquet
    inputs:
      data: enriched
```

```python
from dagcraft import Pipeline, PipelineError

pipeline = Pipeline.from_yaml("pipelines/daily_sales.yaml")  # validates everything

try:
    result = pipeline.run()
except PipelineError as exc:
    print(exc)  # Pipeline 'daily_sales' failed at step ...
    print(exc.result.steps)  # status, duration and error of every step
    raise

result.artifact("enriched")  # the DataFrame produced by a step
```

`inputs` decide the order steps run in: a step runs after every step it
takes input from. Each entry maps a parameter name to the id of the step
whose output it receives.

## Examples

[`config/examples/`](https://github.com/AlexSkowronski/dagcraft/tree/main/config/examples) has pipelines that run on the sample
data in [`data/sample/`](https://github.com/AlexSkowronski/dagcraft/tree/main/data/sample) and write to `output/`:

| Example              | Shows                                                         |
| -------------------- | ------------------------------------------------------------- |
| `basic`              | Read a CSV, drop incomplete rows, write it out.               |
| `local_sales`        | Join CSV and Parquet, filter, aggregate, params.              |
| `json_events`        | Many nested JSON files at once, JSON Lines, YAML.             |
| `excel_reports`      | Several sheets into one table; a workbook with one sheet per input. |
| `sql_reports`        | A `.sql` query file with parameters, reading and writing tables. |
| `azure_blob_to_sql`  | Template: JSON from Azure Blob Storage into Azure SQL.        |
| `sharepoint_reports` | Template: Excel from SharePoint, compared with Azure SQL, published back. |

```bash
dagcraft run config/examples/json_events.yaml
dagcraft run config/examples/sharepoint_reports.yaml --dry-run
```

Regenerate the sample data with `uv run python scripts/make_sample_data.py`.

## Pipeline file

| Key           | Description                                                    |
| ------------- | -------------------------------------------------------------- |
| `pipeline`    | `name` of the pipeline; optionally `max_workers` (see [Running steps in parallel](#running-steps-in-parallel)). |
| `connections` | Optional. Named places to read from and write to (see below).  |
| `steps`       | The steps. Every step has an `id` and a `type`; optionally `inputs`, `retries` and `retry_delay`. |

Relative paths in the file are relative to the file's directory, not to
where the code runs.

### Parameters

Declare values under `params` and use them anywhere in `connections` and
`steps`:

```yaml
params:
  run_date: 2026-10-02
  region: ${env:REGION:-north}

steps:
  - id: orders
    type: read
    connection: lake
    path: orders/${params.run_date}.parquet
```

| Reference                 | Replaced by                                        |
| ------------------------- | -------------------------------------------------- |
| `${params.NAME}`          | The param's value.                                 |
| `${env:NAME}`             | An environment variable. Unset is an error.        |
| `${env:NAME:-default}`    | An environment variable, or `default` if unset.    |
| `$${...}`                 | A literal `${...}`.                                |

A value that is exactly one reference keeps the referenced value's type, so
`columns: ${params.columns}` can be a list. Inside longer text, the value is
inserted as text. Params can use environment variables but not other params.

Override params when loading, from Python or the command line. Overrides
must name a param declared in the file:

```python
Pipeline.from_yaml("pipelines/daily_sales.yaml", params={"run_date": "2026-10-03"})
```

```bash
dagcraft run pipelines/daily_sales.yaml --param run_date=2026-10-03
```

References are resolved when the pipeline is loaded. For secrets, prefer the
connections' `*_env` fields, which read the variable only when connecting.

### Step types

**`read`**: loads data from a connection. Takes no inputs.

| Field        | Description                                                   |
| ------------ | ------------------------------------------------------------- |
| `connection` | Connection name. Defaults to `local`.                         |
| ...          | The remaining fields depend on the connection type (see below). |

**`write`**: saves its input to a connection, and passes it on as its own
output.

| Field        | Description                                                   |
| ------------ | ------------------------------------------------------------- |
| `connection` | Connection name. Defaults to `local`.                         |
| `inputs`     | One input, e.g. `{data: enriched}`. Formats that hold several tables, such as Excel, take several. |
| ...          | The remaining fields depend on the connection type.           |

**`transform`**: calls a registered operation with its inputs and `args` as
keyword arguments.

| Field       | Description                                    |
| ----------- | ---------------------------------------------- |
| `operation` | Name of a built-in or registered operation.    |
| `args`      | Extra keyword arguments for the operation.     |

**`python`**: like `transform`, but calls any importable function.

| Field      | Description                                         |
| ---------- | --------------------------------------------------- |
| `callable` | `module.path:function_name`                         |
| `args`     | Extra keyword arguments for the function.           |

### Built-in operations

| Operation    | Inputs          | Args                                         |
| ------------ | --------------- | -------------------------------------------- |
| `drop_nulls` | `data`          | `subset` (optional list of columns)          |
| `filter`     | `data`          | `expression` (a `DataFrame.query` expression) |
| `select`     | `data`          | `columns` (list)                             |
| `rename`     | `data`          | `columns` (mapping of old name to new name)  |
| `sort`       | `data`          | `by` (column or list), `ascending` (default `true`) |
| `join`       | `left`, `right` | `on`, plus any `DataFrame.merge` argument, such as `how` |
| `aggregate`  | `data`          | `by` (column or list), `columns` (mapping of column to `sum`, `mean`, `count`, `min`, `max`, ...) |

## Connections

A `local` connection, rooted at the pipeline file's directory, is always
available. Define others under `connections`, each with a `type`.

### File connections: `local`, `azure_blob` and `sharepoint`

Read and write steps on file connections take:

| Field           | Description                                                 |
| --------------- | ----------------------------------------------------------- |
| `path`          | File path, relative to the connection's root. Reads can use wildcards. |
| `format`        | Optional when the extension says which (see below).        |
| `args`          | Passed to the format's reader or writer, e.g. `{sep: ";"}`. |
| `source_column` | Reads with wildcards: a column naming each row's file.      |

| Format    | Extensions         | Notes                                              |
| --------- | ------------------ | -------------------------------------------------- |
| `csv`     | `.csv`             | `args` go to `pandas.read_csv` / `to_csv`.         |
| `parquet` | `.parquet`, `.pq`  | `args` go to `pandas.read_parquet` / `to_parquet`. |
| `excel`   | `.xlsx`, `.xlsm`   | Needs `dagcraft-pipelines[excel]`. See below.                |
| `json`    | `.json`            | Nested objects become dotted columns (`user.id`). `args` go to `pandas.json_normalize`, e.g. `record_path` and `meta`. |
| `jsonl`   | `.jsonl`, `.ndjson`| One JSON record per line; read like `json`.        |
| `yaml`    | `.yaml`, `.yml`    | Read like `json`.                                  |

Writes leave out the DataFrame index unless `args` sets `index: true`.

#### Many files at once

A read `path` with wildcards (`*`, `?`, `[...]`, and `**` for any depth)
reads every matching file into one table, in path order. No matching files
is an error.

```yaml
  - id: events
    type: read
    connection: lake
    path: events/2026-10-*.json
    source_column: source_file    # which file each row came from
    args:
      record_path: events         # the records inside each document
      meta: [batch_id]            # document fields to copy onto each record
```

#### Excel sheets

| `args`                        | Reads                                                   |
| ----------------------------- | ------------------------------------------------------- |
| (none)                        | The first sheet.                                        |
| `sheet_name: Targets`         | One sheet.                                              |
| `sheet_name: [North, South]`  | Those sheets, as one table with a `sheet` column naming each row's sheet. |
| `sheet_name: null`            | Every sheet, as one table.                              |
| `sheet_column: region`        | With several sheets: renames the `sheet` column.        |

Sheets with different columns are best read by separate steps.

A write step with several inputs writes a workbook with one sheet per
input, named after the input:

```yaml
  - id: report
    type: write
    path: reports/regional.xlsx
    inputs:
      Summary: totals
      Monthly: monthly
```

**`local`**

| Field  | Description                                                   |
| ------ | ------------------------------------------------------------- |
| `root` | Directory paths are relative to. Defaults to the file's directory. |

**`azure_blob`**: Azure Blob Storage, including ADLS Gen2 accounts.
Requires `dagcraft-pipelines[azure]`.

| Field                   | Description                                             |
| ----------------------- | ------------------------------------------------------- |
| `container`             | Container name.                                         |
| `prefix`                | Optional folder inside the container.                   |
| `account`               | Storage account; sign in with `DefaultAzureCredential`. |
| `connection_string_env` | Or: environment variable holding a connection string.   |

Set exactly one of `account` or `connection_string_env`.
`DefaultAzureCredential` uses your `az login` locally, managed identity in
Azure, or service principal environment variables. If
`AZURE_STORAGE_CONNECTION_STRING` is set, signing in with `account` is
refused: the underlying library would quietly use that connection string
instead, possibly for a different account.

**`sharepoint`**: a SharePoint document library, through Microsoft Graph.
Requires `dagcraft-pipelines[azure]`.

| Field     | Description                                                     |
| --------- | --------------------------------------------------------------- |
| `site`    | The site's address, e.g. `contoso.sharepoint.com/sites/Finance`. |
| `library` | Document library name. Defaults to `Documents`.                 |
| `folder`  | Optional folder inside the library.                             |

dagcraft signs in with `DefaultAzureCredential`, so the identity (usually a
service principal) needs Microsoft Graph permission to the site's files,
such as `Sites.Selected` or `Sites.ReadWrite.All`. Wildcards work in file
names but not folder names, uploads are limited to 250 MB, and throttled
requests are retried.

### SQL connections: `sql` and `azure_sql`

Read steps take a `query`, a `query_file` or a `table`:

| Field        | Description                                                 |
| ------------ | ----------------------------------------------------------- |
| `query`      | SQL to run. Use `:name` placeholders for `params`.          |
| `query_file` | Or: a `.sql` file, relative to the pipeline file. Same placeholders. |
| `table`      | Or: a whole table, as `name` or `schema.name`.              |
| `params`     | Values for the query's placeholders.                        |
| `args`       | Passed to `pandas.read_sql`.                                |
| `partition`  | Read a large result in parallel parts (see below).          |

Only `:name` in SQL code is a placeholder; inside comments and string
literals it's left alone, so a `.sql` file can document its parameters.

#### Large reads in parallel parts

`partition` splits a big read into ranges of a whole-number column (such as
an ID) and reads them at the same time, each on its own connection, then
combines them. It's typically a few times faster on a large table, if the
database has the capacity; it isn't linear, because turning rows into a
DataFrame still happens on one CPU core.

```yaml
  - id: orders
    type: read
    connection: warehouse
    table: dbo.orders
    partition:
      column: order_id   # its MIN and MAX set the range
      parts: 8           # 2 to 32
```

Rows where the column is NULL are read too. Set `lower` and `upper` to read
only that range instead of finding it with MIN and MAX.

For a `query` or `query_file`, put `:partition_start` and `:partition_end`
where the range belongs and give the bounds; dagcraft never rewrites your
SQL, so this works with CTEs and anything else:

```yaml
    query_file: sql/orders.sql   # ... WHERE o.order_id BETWEEN :partition_start AND :partition_end
    partition:
      parts: 8
      lower: 1
      upper: 50000000
```

Write steps take:

| Field       | Description                                                    |
| ----------- | -------------------------------------------------------------- |
| `table`     | `name` or `schema.name`.                                       |
| `if_exists` | `fail` (default), `append`, `delete_rows` (empty the table but keep its definition) or `replace` (drop and recreate it). |
| `args`      | Passed to `DataFrame.to_sql`, e.g. `dtype` or `chunksize`.     |

Each write runs in a single transaction, so a failure part-way leaves the
table as it was.

```yaml
  - id: customers
    type: read
    connection: warehouse
    query_file: sql/new_customers.sql   # ... WHERE created_at >= :since
    params:
      since: ${params.run_date}
```

**`sql`**: any database SQLAlchemy supports. Requires `dagcraft-pipelines[sql]` and
a driver for your database (SQLite needs none).

| Field     | Description                                                     |
| --------- | --------------------------------------------------------------- |
| `url`     | Database URL, e.g. `sqlite:///data/local.db`.                   |
| `url_env` | Or: environment variable holding the URL, for URLs with passwords. |

**`azure_sql`**: Azure SQL Database or SQL Server. Requires
`dagcraft-pipelines[azure]` and the ODBC driver.

| Field                   | Description                                             |
| ----------------------- | ------------------------------------------------------- |
| `server`                | e.g. `myserver.database.windows.net`                    |
| `database`              | Database name.                                          |
| `driver`                | ODBC driver. Defaults to `ODBC Driver 18 for SQL Server`. |
| `connection_string_env` | Or: environment variable holding an ODBC connection string. |

With `server` and `database`, dagcraft signs in with an Entra ID token from
`DefaultAzureCredential`. A fresh token is fetched for each new database
connection, so long runs aren't cut off when a token expires. Use
`connection_string_env` for anything else, such as SQL authentication.
Writes use pyodbc's `fast_executemany`.

## Validation

`Pipeline.from_yaml` checks the whole file before anything runs: every field
of every step and connection, that the operations, functions, connections
and formats it names exist, and that the steps form a graph without cycles.
Problems raise `ConfigError` with one line per problem:

```
dagcraft.exceptions.ConfigError: Step 'orders': pth: Extra inputs are not permitted
```

Things that depend on the machine, such as environment variables, ODBC
drivers and credentials, are checked when a connection is first used.

To check a pipeline and see what it would do without running it, use
`dagcraft run ... --dry-run`, or `pipeline.plan()` from Python:

```
INFO | Pipeline 'sql_reports' is valid.
INFO | Params: data_dir=../../data/sample, output_dir=../../output, since=2026-09-15, status=shipped
INFO | Steps, in run order:
INFO |   1. revenue_by_region  read the query in sql/revenue_by_region.sql from 'warehouse'
INFO |   2. products           read table products from 'warehouse'
INFO |   3. save_revenue       write table revenue_by_region (if it exists: replace) to 'reports'  <- data: revenue_by_region
INFO |   4. save_products      write table products (if it exists: replace) to 'reports'  <- data: products
INFO | Dry run: nothing was run.
```

To prove the connections work before a run, use `--check-connections`, or
`pipeline.check_connections()` from Python. Each connection the steps use is
opened and does one cheap real operation, so problems with credentials,
permissions, network or drivers show up in seconds without touching data:

| Connection   | Check                                                         |
| ------------ | ------------------------------------------------------------- |
| `local`      | The folder exists (or will be created when writing).          |
| `azure_blob` | Lists the container, and whether the prefix has files.        |
| `sharepoint` | Finds the site and library, and lists the folder.             |
| `sql`        | Runs `SELECT 1`.                                              |
| `azure_sql`  | Connects and reports the login and database, so you can see which identity `DefaultAzureCredential` picked. |

```
INFO | Checking 3 connection(s):
INFO |   lake       azure_blob  OK      container 'raw' is reachable; prefix 'events' has files
ERROR|   finance    sharepoint  FAILED  SharePoint returned 403 for GET https://graph.microsoft.com/...: Access denied.
INFO |   warehouse  azure_sql   OK      connected to analytics as etl-app@contoso.com
ERROR| 1 of 3 connection(s) failed.
```

## Running and failures

Steps run in the order they're written, except where a step has to wait for
its inputs.

When a step fails, the steps that depend on it, directly or further down,
are skipped, and every other step still runs. `run()` then raises
`PipelineError` naming each failed step. Its `result` holds every step's
status (`SUCCESS`, `FAILED` or `SKIPPED`), and the first failure's exception
is chained, so the traceback shows the real cause.

To stop at the first failure instead:

```python
pipeline.run(fail_fast=True)
```

For steps that can fail for a moment, such as reading over a network or
connecting to a database that's waking up, add retries. The step runs again
up to `retries` more times, waiting `retry_delay` seconds (default 5) before
the first retry and twice as long before each one after:

```yaml
  - id: orders
    type: read
    connection: warehouse
    table: dbo.orders
    retries: 3          # waits 10s, 20s, then 40s
    retry_delay: 10
```

SQL writes run in a transaction, uploads to Azure Blob Storage and
SharePoint replace the file in one go, and local files are written to a
temporary name first, so retrying a write is safe.

### Running steps in parallel

Steps that don't depend on each other can run at the same time, which helps
when a pipeline runs several queries or downloads:

```yaml
pipeline:
  name: daily_sales
  max_workers: 4    # up to 4 independent steps at once; default 1
```

Override it with `pipeline.run(max_workers=8)` or `--max-workers 8`. Steps
still start in the order they're written, and each waits for its inputs. With
more than one worker, steps run in threads, so functions you call from
`python` steps or register as operations should be safe to run alongside
each other.

Every step's output stays available on the result (`result.artifact(id)`)
until the run ends. For large data, drop each output as soon as the steps
that use it have finished instead (the command line always does this):

```python
pipeline.run(keep_artifacts=False)
```

## Logging

dagcraft logs to the `dagcraft` logger and, like any library, prints nothing
unless your application configures logging:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

Every run has an ID, and each message from the run starts with the pipeline
and run ID, so runs can be told apart in shared logs:

```
INFO | [daily_sales 3f2a9c1b] Running step 'orders'
```

The records also carry `pipeline` and `run_id` attributes, for log
handlers that store fields (such as Azure Monitor). The ID is random unless
you pass one, for example your orchestrator's run ID, and it's on the
result:

```python
result = pipeline.run(run_id="adf-5c1e")
result.run_id
```

## Command line

```bash
dagcraft run pipelines/daily_sales.yaml --dry-run
dagcraft run pipelines/daily_sales.yaml --param run_date=2026-10-03
```

| Option                | Effect                                                     |
| --------------------- | ---------------------------------------------------------- |
| `--dry-run`           | Check the pipeline and show the steps it would run. Handy in CI. |
| `--check-connections` | Check the pipeline and prove each connection it uses works (see below). |
| `--param NAME=VALUE`  | Override a param. Values are read as YAML. Repeatable.     |
| `--fail-fast`         | Skip every remaining step after the first failure.         |
| `--max-workers N`     | Run up to N independent steps at once.                     |
| `--run-id ID`         | ID for the run in the logs, e.g. from an orchestrator.     |

The command exits with status 1 if the pipeline is invalid or a step fails.

## Extending dagcraft

Register your own components before loading a pipeline that uses them,
for example by importing the module that defines them.

**Operations** for `transform` steps:

```python
from dagcraft import register_operation


@register_operation("add_total")
def add_total(data, columns, name="total"):
    return data.assign(**{name: data[columns].sum(axis=1)})
```

**Step types**, with their own validated fields:

```python
from dagcraft import BaseStep, StepConfig, register_step


class SampleConfig(StepConfig):
    fraction: float


@register_step("sample")
class SampleStep(BaseStep):
    config_model = SampleConfig
    config: SampleConfig

    def execute(self, context, inputs):
        (data,) = inputs.values()
        return data.sample(frac=self.config.fraction, random_state=0)
```

**Connections**: subclass `FsspecConnection` for anything
[fsspec](https://filesystem-spec.readthedocs.io/) can reach, `FileConnection`
for other file storage (implement `open_file`, and `glob` for wildcards), or
`Connection` for anything else, and use `register_connection`. Override
`check()` so `--check-connections` can prove the connection works.
**Formats**: subclass `Format` and use `register_format`.

## Security

A pipeline file can run code: `python` steps import and call functions, and
`filter` expressions are evaluated by pandas. Only run pipeline files you
trust, as you would any other code.

## Development

```bash
uv sync                    # installs dev tools, including the optional extras
uv run pre-commit install  # lint, format and type checks on commit; tests on push
uv run pytest
```

CI runs the same checks, builds the package, and runs the tests on
Python 3.11 to 3.14 on Linux and on Windows.

### Releasing

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

Before the first release, add a trusted publisher on PyPI (Your account →
Publishing → Add a new pending publisher) with project name
`dagcraft-pipelines`, owner `AlexSkowronski`, repository `dagcraft`, workflow
`release.yml` and environment `pypi`.

## License

MIT
