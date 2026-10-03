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
from dagcraft import Pipeline, RunError, configure_logging

configure_logging()  # print progress to the console; optional

pipeline = Pipeline.from_yaml("pipelines/daily_sales.yaml")  # validates everything

try:
    result = pipeline.run()
except RunError as exc:
    print(exc)  # Pipeline 'daily_sales' failed at step ...
    print(exc.result.steps)  # status, duration and error of every step
    raise

result.output("enriched")  # the DataFrame produced by a step
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
dagcraft config/examples/json_events.yaml
dagcraft config/examples/sharepoint_reports.yaml --dry-run
```

Regenerate the sample data with `uv run python scripts/make_sample_data.py`.

## Pipeline file

| Key           | Description                                                    |
| ------------- | -------------------------------------------------------------- |
| `pipeline`    | `name` of the pipeline; optionally `max_workers` (see [Running steps in parallel](#running-steps-in-parallel)) and `env_file` (see [Secrets](#secrets-and-env-files)). |
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

To vary a value between runs, give it an environment variable with a
default, as `region` does above. From Python you can also override params
when loading; overrides must name a param declared in the file:

```python
Pipeline.from_yaml("pipelines/daily_sales.yaml", params={"run_date": "2026-10-03"})
```

References are resolved when the pipeline is loaded, so an unset variable
is reported before anything runs.

### Secrets and .env files

Keep connection strings and passwords out of pipeline files: write them as
`${env:NAME}`. dagcraft holds them as secrets, so they never appear in
reprs, logs or error messages.

```yaml
pipeline:
  name: daily_sales
  env_file: .env      # optional: load variables from this file first

connections:
  lake:
    type: azure_blob
    container: raw
    connection_string: ${env:LAKE_CONNECTION_STRING}
```

`env_file` is relative to the pipeline file and loaded before anything else.
Variables already set in the environment keep their values, so a scheduler
or CI secret wins over the file. They go into the process environment, so
`DefaultAzureCredential` can use a service principal's `AZURE_CLIENT_ID`,
`AZURE_TENANT_ID` and `AZURE_CLIENT_SECRET` from the file too. Don't commit
`.env` files.

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

A read or write step combines three things, each with one job:

| Piece                   | Job                                   | Built in                                    |
| ----------------------- | ------------------------------------- | ------------------------------------------- |
| Connection              | Where the data is, and signing in     | `local`, `azure_blob`, `sharepoint`, `sql`, `azure_sql` |
| Reader / writer         | What to read or write there           | Files (`path`), SQL (`query`, `table`)      |
| Format (files only)     | How a file's bytes become a table     | `csv`, `parquet`, `excel`, `json`, `jsonl`, `yaml` |

So the fields a step takes depend on its connection's kind: file
connections take a `path`, SQL connections a `query` or `table`.

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

| Field               | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| `container`         | Container name.                                             |
| `prefix`            | Optional folder inside the container.                       |
| `account`           | Storage account; sign in with `DefaultAzureCredential`.     |
| `connection_string` | Or: a connection string, usually `${env:NAME}`.             |

Set exactly one of `account` or `connection_string`.
`DefaultAzureCredential` uses service principal environment variables if
set, managed identity in Azure, or your `az login`. If the
`AZURE_STORAGE_CONNECTION_STRING` environment variable is set, signing in
with `account` is refused: the underlying library (adlfs) would quietly use
that connection string instead, possibly for a different account.

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
names but not folder names (checked when the pipeline loads), uploads are
limited to 250 MB, and throttled requests are retried.

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

| Field | Description                                                         |
| ----- | ------------------------------------------------------------------- |
| `url` | Database URL, e.g. `sqlite:///data/local.db`. Write URLs with passwords as `${env:NAME}`. |

For example, Postgres with `pip install psycopg`:
`url: postgresql+psycopg://etl@dbhost/analytics`.

**`azure_sql`**: Azure SQL Database or SQL Server. Requires
`dagcraft-pipelines[azure]` and the ODBC driver.

| Field               | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| `server`            | e.g. `myserver.database.windows.net`                        |
| `database`          | Database name.                                              |
| `driver`            | ODBC driver. Defaults to `ODBC Driver 18 for SQL Server`.   |
| `connection_string` | Or: a full ODBC connection string, usually `${env:NAME}`.   |

With `server` and `database`, dagcraft signs in with an Entra ID token from
`DefaultAzureCredential` (your `az login` locally). A fresh token is fetched
for each new database connection, so long runs aren't cut off when a token
expires. Use `connection_string` for anything else, such as SQL
authentication. Writes use pyodbc's `fast_executemany`.

## Validation

`Pipeline.from_yaml` checks the whole file before anything runs: every field
of every step and connection, that the operations, functions, connections
and formats it names exist, and that the steps form a graph without cycles.
Problems raise `ConfigError` with one line per problem:

```
dagcraft.exceptions.ConfigError: Step 'orders': pth: Extra inputs are not permitted
```

Environment variables are checked then too. Things that depend on the
machine and network, such as ODBC drivers and credentials, are checked when
a connection is first used.

To check a pipeline and see what it would do without running it, use
`dagcraft pipeline.yaml --dry-run`, or `pipeline.plan()` from Python:

```
2026-10-03 08:43:38 INFO    Pipeline 'sql_reports' is valid.
2026-10-03 08:43:38 INFO    Params: data_dir=../../data/sample, output_dir=../../output, since=2026-09-15, status=shipped
2026-10-03 08:43:38 INFO    Steps, in run order:
2026-10-03 08:43:38 INFO      1. revenue_by_region  read the query in sql/revenue_by_region.sql from 'warehouse'
2026-10-03 08:43:38 INFO      2. products           read table products from 'warehouse'
2026-10-03 08:43:38 INFO      3. save_revenue       write table revenue_by_region (if it exists: replace) to 'reports'  <- data: revenue_by_region
2026-10-03 08:43:38 INFO      4. save_products      write table products (if it exists: replace) to 'reports'  <- data: products
2026-10-03 08:43:38 INFO    Dry run: nothing was run.
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
INFO    Checking 3 connection(s):
INFO      lake       azure_blob  OK      container 'raw' is reachable; prefix 'events' has files
ERROR     finance    sharepoint  FAILED  SharePoint returned 403 for GET https://graph.microsoft.com/...: Access denied.
INFO      warehouse  azure_sql   OK      connected to analytics as etl-app@contoso.com
ERROR   1 of 3 connection(s) failed.
```

## Running and failures

Steps run in the order they're written, except where a step has to wait for
its inputs.

When a step fails, the steps that depend on it, directly or further down,
are skipped, and every other step still runs. `run()` then raises
`RunError` naming each failed step. Its `result` holds every step's
status (`SUCCESS`, `FAILED` or `SKIPPED`), and the first failure's exception
is chained, so the traceback shows the real cause.

Every error dagcraft raises is a `PipelineError`:

| Error            | Raised when                                                |
| ---------------- | ---------------------------------------------------------- |
| `ConfigError`    | The pipeline file is invalid (raised when loading).        |
| `GraphError`     | A kind of `ConfigError`: a cycle, or an unknown input.     |
| `ExecutionError` | A step or connection couldn't do its work.                 |
| `RunError`       | `run()` had failed steps; `.result` has the details.       |

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

Every step's output stays available on the result (`result.output(id)`)
until the run ends. For large data, drop each output as soon as the steps
that use it have finished instead (the command line always does this):

```python
pipeline.run(keep_outputs=False)
```

## Logging

Each step logs when it starts, what it did and how long it took:

```
2026-10-03 08:43:40 INFO    [basic 4b554a3c] Starting run: 3 steps
2026-10-03 08:43:40 INFO    [basic 4b554a3c] employees: started: read employees.csv from 'data'
2026-10-03 08:43:40 INFO    [basic 4b554a3c] employees: finished in 0.008s: 5 rows x 4 columns
2026-10-03 08:43:40 INFO    [basic 4b554a3c] salaried: started: transform with 'drop_nulls'
2026-10-03 08:43:40 INFO    [basic 4b554a3c] salaried: finished in 0.003s: 4 rows x 4 columns
2026-10-03 08:43:40 INFO    [basic 4b554a3c] save: started: write basic/salaried.csv to 'output'
2026-10-03 08:43:40 INFO    [basic 4b554a3c] save: finished in 0.003s: 4 rows x 4 columns
2026-10-03 08:43:40 INFO    [basic 4b554a3c] Run succeeded in 0.014s
```

Long reads add progress lines, such as how many files a wildcard matched or
how many parts a partitioned read runs in. Detail, such as each file and
each SQL part, is logged at DEBUG (`-v` on the command line). Retries and
skipped steps are warnings; failures are errors with the traceback.

Every message during a run starts with the pipeline, the run ID and the
step, so runs can be told apart in shared logs. The records also carry
`pipeline`, `run_id` and `step` attributes, for log handlers that store
fields (such as Azure Monitor). The run ID is random unless you pass one,
for example your orchestrator's, and it's on the result:

```python
result = pipeline.run(run_id="adf-5c1e")
result.run_id
```

Like any library, dagcraft prints nothing until logging is configured. In a
script, `configure_logging()` prints dagcraft's messages with timestamps
(other libraries' only from WARNING up, since the Azure SDK logs every
request at INFO):

```python
from dagcraft import Pipeline, configure_logging

configure_logging()           # or configure_logging(logging.DEBUG)
Pipeline.from_yaml("pipelines/daily_sales.yaml").run()
```

In an application with its own logging setup, configure the `dagcraft`
logger instead. Modules log under it by name (`dagcraft.readers.files`,
`dagcraft.core.step_runner`, ...), so you can tune parts separately.

`Timer` measures how long something takes, as a context manager or a
decorator, and can log it:

```python
from dagcraft import Timer

with Timer() as timer:
    pipeline.run()
print(f"{timer.elapsed:.1f}s")

@Timer("refresh", logger=logging.getLogger(__name__))
def refresh(): ...
```

## Command line

```bash
dagcraft pipelines/daily_sales.yaml                      # check, then run
dagcraft pipelines/daily_sales.yaml --dry-run            # check and show the plan
dagcraft pipelines/daily_sales.yaml --check-connections  # check and sign in to each connection
```

`python -m dagcraft ...` does the same, where the `dagcraft` script isn't on
the PATH.

| Option                | Effect                                                     |
| --------------------- | ---------------------------------------------------------- |
| `--dry-run`           | Check the pipeline and show the steps it would run. Handy in CI. |
| `--check-connections` | Check the pipeline and prove each connection it uses works (see [Validation](#validation)). |
| `--fail-fast`         | Skip every remaining step after the first failure.         |
| `--max-workers N`     | Run up to N independent steps at once.                     |
| `--run-id ID`         | ID for the run in the logs, e.g. from an orchestrator.     |
| `-v`, `--verbose`     | Also log detail, such as each file and each SQL part read. |

| Exit status | Meaning                                         |
| ----------- | ----------------------------------------------- |
| 0           | Success.                                        |
| 1           | A step or a connection check failed.            |
| 2           | The pipeline file is invalid, or the arguments. |

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

Steps of your own can log with `context.logger`, or with
`dagcraft.get_logger(__name__)` from any module; either way, messages carry
the run and step.

**Connections** handle signing in and holding a client; readers and
writers handle what's read and written. For other file storage, subclass
`FileConnection` and implement `open_file`, `glob` and `check`: the built-in
file reader, writer and formats then work with it. For a different kind of
source, subclass `Connection` and register a reader (and writer) for it:

```python
from pydantic import BaseModel

from dagcraft import Connection, Reader, register_connection, register_reader


class ApiConfig(BaseModel):
    base_url: str


class ApiReadOptions(BaseModel):
    endpoint: str


@register_connection("api")
class ApiConnection(Connection):
    config_model = ApiConfig

    def open(self): ...   # sign in, create a session
    def close(self): ...
    def check(self):      # one cheap real request, for --check-connections
        return "reachable"


@register_reader(ApiConnection)
class ApiReader(Reader):
    options_model = ApiReadOptions   # the read step's fields

    def read(self, connection):
        ...  # fetch self.options.endpoint with the connection's session
```

**Formats**: subclass `Format` and use `register_format`. **Writers**:
subclass `Writer` and use `register_writer`.

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

Type checking uses Pyright, the checker behind VS Code's Pylance, so the
editor and the hooks report the same problems. CI runs the same checks,
builds the package, and runs the tests on Python 3.11 to 3.14 on Linux and
on Windows.

The source is organised by job, one concern per module:

```
src/dagcraft/
  config/        what a pipeline file can say: pydantic models only
  core/          compiling and running: graph, scheduler, step runner, ...
  connections/   where data lives and signing in: files/ and sql/
  readers/       what a read step fetches, per kind of connection
  writers/       what a write step puts, per kind of connection
  formats/       how a file becomes a table, one format per module
  steps/         read, write, transform, python
  operations/    built-in transform operations
  cli/           the dagcraft command: arguments, main, report
  logs.py        run and step context for log messages
```

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
