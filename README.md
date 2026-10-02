# dagcraft

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
pip install dagcraft            # local files: CSV and Parquet
pip install 'dagcraft[sql]'     # + SQL databases through SQLAlchemy
pip install 'dagcraft[azure]'   # + Azure Blob Storage and Azure SQL
```

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

## Pipeline file

| Key           | Description                                                    |
| ------------- | -------------------------------------------------------------- |
| `pipeline`    | `name` of the pipeline.                                        |
| `connections` | Optional. Named places to read from and write to (see below).  |
| `steps`       | The steps. Every step has an `id`, a `type` and, optionally, `inputs`. |

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

**`write`**: saves its single input to a connection, and passes it on as its
own output.

| Field        | Description                                                   |
| ------------ | ------------------------------------------------------------- |
| `connection` | Connection name. Defaults to `local`.                         |
| `inputs`     | Exactly one input, e.g. `{data: enriched}`.                   |
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

## Connections

A `local` connection, rooted at the pipeline file's directory, is always
available. Define others under `connections`, each with a `type`.

### File connections: `local` and `azure_blob`

Read and write steps on file connections take:

| Field    | Description                                                        |
| -------- | ------------------------------------------------------------------ |
| `path`   | File path, relative to the connection's root.                      |
| `format` | `csv` or `parquet`. Optional when the extension says which.        |
| `args`   | Passed to pandas (`read_csv`, `to_parquet`, ...), e.g. `{sep: ";"}`. |

Writes leave out the DataFrame index unless `args` sets `index: true`.

**`local`**

| Field  | Description                                                   |
| ------ | ------------------------------------------------------------- |
| `root` | Directory paths are relative to. Defaults to the file's directory. |

**`azure_blob`**: Azure Blob Storage, including ADLS Gen2 accounts.
Requires `dagcraft[azure]`.

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

### SQL connections: `sql` and `azure_sql`

Read steps take a `query` or a `table`:

| Field    | Description                                                    |
| -------- | -------------------------------------------------------------- |
| `query`  | SQL to run. Use `:name` placeholders for `params`.             |
| `params` | Values for the query's placeholders.                           |
| `table`  | Or: a whole table, as `name` or `schema.name`.                 |
| `args`   | Passed to `pandas.read_sql`.                                   |

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
    query: |
      SELECT id, region
      FROM dbo.customers
      WHERE created_at >= :since
    params:
      since: 2026-01-01
```

**`sql`**: any database SQLAlchemy supports. Requires `dagcraft[sql]` and
a driver for your database (SQLite needs none).

| Field     | Description                                                     |
| --------- | --------------------------------------------------------------- |
| `url`     | Database URL, e.g. `sqlite:///data/local.db`.                   |
| `url_env` | Or: environment variable holding the URL, for URLs with passwords. |

**`azure_sql`**: Azure SQL Database or SQL Server. Requires
`dagcraft[azure]` and the ODBC driver.

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

## Logging

dagcraft logs to the `dagcraft` logger and, like any library, prints nothing
unless your application configures logging:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

## Command line

```bash
dagcraft validate pipelines/daily_sales.yaml
dagcraft run pipelines/daily_sales.yaml --param run_date=2026-10-03
```

`validate` is handy in CI. Both take `--param NAME=VALUE` (values are read
as YAML) and exit with status 1 on failure.

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

**Connections**: subclass `FileConnection` for anything
[fsspec](https://filesystem-spec.readthedocs.io/) can reach, or `Connection`
for anything else. **Formats**: subclass `Format` and use
`register_format`.

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

## License

MIT
