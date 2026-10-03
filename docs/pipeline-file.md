# The pipeline file

A pipeline file has four sections:

```yaml
pipeline:          # about the pipeline itself
  name: daily_sales
  max_workers: 1   # optional: independent steps to run at once
  env_file: .env   # optional: load environment variables first

params:            # optional: values to use in the rest of the file
  run_date: 2026-10-02

connections:       # optional: where data lives (local files need none)
  lake:
    type: azure_blob
    account: mystorageaccount
    container: raw

steps:             # what to do
  - id: orders
    type: read
    connection: lake
    path: orders/${params.run_date}.parquet
```

| Section | |
| --- | --- |
| `pipeline` | `name` (required), `max_workers` (see [parallel steps](running.md#running-steps-in-parallel)), `env_file` (see [below](#env-files)). |
| `params` | Named values, used as `${params.NAME}`. |
| `connections` | Named connections, each with a `type`. A `local` one is always there. See [Connections](connections/local.md). |
| `steps` | The steps. See [Steps and operations](steps.md). |

## Params and references

Write `${...}` anywhere in `params`, `connections` or `steps`:

| Reference | Replaced by |
| --- | --- |
| `${params.NAME}` | A param's value. |
| `${env:NAME}` | An environment variable. If it's unset, the pipeline won't load. |
| `${env:NAME:-default}` | An environment variable, or `default` if it's unset. |
| `$${...}` | A literal `${...}`. |

```yaml
params:
  run_date: ${env:RUN_DATE:-2026-10-02}   # RUN_DATE, or a default
  region: north

steps:
  - id: orders
    type: read
    path: data/${params.region}/${params.run_date}.csv
```

- A value that's exactly one reference keeps its type, so
  `columns: ${params.columns}` can be a list. Inside longer text, the value
  is inserted as text.
- Params can use environment variables, but not other params.
- From Python, you can override params when loading, by name:
  `Pipeline.from_yaml(path, params={"run_date": "2026-10-03"})`.

To vary a value between runs without changing the file, give it an
environment variable with a default, as `run_date` does above.

## .env files

`env_file` loads environment variables from a file before anything else is
read, so `${env:...}` references can use them:

```
# .env, in the folder you run from
SQL_SERVER=myserver.database.windows.net
SQL_DATABASE=analytics
LAKE_CONNECTION_STRING='DefaultEndpointsProtocol=https;AccountName=...'
```

```yaml
pipeline:
  name: daily_sales
  env_file: .env

connections:
  warehouse:
    type: azure_sql
    server: ${env:SQL_SERVER}
    database: ${env:SQL_DATABASE}
```

- The path is relative to the folder you run from.
- Variables already set in the environment win, so a scheduler can override
  the file.
- A service principal's `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and
  `AZURE_CLIENT_SECRET` in the file are used for Azure sign-in too.
- Don't commit `.env` files.

## Secrets

Write connection strings and URLs with passwords as `${env:NAME}`, never in
the file itself. dagcraft keeps them as secrets: they don't appear in logs,
error messages or printed configs.

```yaml
connections:
  lake:
    type: azure_blob
    container: raw
    connection_string: ${env:LAKE_CONNECTION_STRING}
```

## Checked when it loads

`Pipeline.from_yaml` checks the whole file before anything runs: every field
of every step and connection, that the operations, functions, connections,
formats and query files it names exist, and that the steps form a graph
without cycles. A problem raises `ConfigError` with one line per problem:

```
ConfigError: Step 'orders': pth: Extra inputs are not permitted
```

Things that depend on the machine and network, such as drivers and
credentials, are checked when a connection is first used, or with
[`--check-connections`](running.md#checking-connections).
