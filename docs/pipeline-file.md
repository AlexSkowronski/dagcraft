# The pipeline file

A pipeline file has these sections:

```yaml
pipeline:          # about the pipeline itself
  name: daily_sales
  max_workers: 1   # optional: independent steps to run at once
  env_file: .env   # optional: load environment variables first
  imports:         # optional: your modules that register operations and so on
    - my_project.cleaning

include:           # optional: files of shared connections
  - connections.yaml

params:            # optional: values to use in the rest of the file
  region: north

connections:       # optional: where data lives (local files need none)
  lake:
    type: azure_blob
    account: mystorageaccount
    container: raw

steps:             # what to do
  - id: orders
    type: read
    connection: lake
    path: orders/${params.region}/${run_date}.parquet
```

| Section | |
| --- | --- |
| `pipeline` | `name` (required), `max_workers` (see [parallel steps](running.md#running-steps-in-parallel)), `env_file` (see [below](#env-files)), `imports` (see [below](#your-own-modules)). |
| `include` | Files of [shared connections](#sharing-connections). |
| `params` | Named values, used as `${params.NAME}`. |
| `connections` | Named connections, each with a `type`. A `local` one is always there. See [Connections](connections/local.md). |
| `steps` | The steps. See [Steps and operations](steps.md). |

## Sharing connections

Pipelines in one project usually use the same connections. Define them once
in a file of their own and `include` it:

```yaml
# connections.yaml, in the folder you run from
connections:
  lake:
    type: azure_blob
    account: ${env:STORAGE_ACCOUNT}
    container: raw
  warehouse:
    type: azure_sql
    server: ${env:SQL_SERVER}
    database: ${env:SQL_DATABASE}
```

```yaml
# configs/events_to_sql.yaml
pipeline:
  name: events_to_sql
  env_file: .env

include:
  - connections.yaml

steps:
  - id: batches
    type: read
    connection: lake
    path: events/*.json
```

- An included file holds only `connections`. Its path is relative to the
  folder you run from.
- Only the connections a pipeline's steps use are opened or checked, so a
  shared file can list every connection the project has.
- A connection the pipeline defines itself, under its own `connections`,
  replaces a shared one of the same name: say, `warehouse` pointing at a
  test database.
- Two included files defining the same connection is an error.
- Errors in a shared connection name its file:
  `Connection 'lake' (from connections.yaml): container: Field required`.

## Params and references

Write `${...}` anywhere in `params`, `connections` or `steps`:

| Reference | Replaced by |
| --- | --- |
| `${params.NAME}` | A param's value. |
| `${run_date}` | The day the run is for, such as `2026-10-17`: today, unless [set](#the-run-date). |
| `${env:NAME}` | An environment variable. If it's unset, the pipeline won't load. |
| `${env:NAME:-default}` | An environment variable, or `default` if it's unset. |
| `$${...}` | A literal `${...}`. |

```yaml
params:
  region: ${env:REGION:-north}   # REGION, or a default

steps:
  - id: orders
    type: read
    path: data/${params.region}/${run_date}.csv
```

- A value that's exactly one reference keeps its type, so
  `columns: ${params.columns}` can be a list. Inside longer text, the value
  is inserted as text.
- Params can use environment variables and `${run_date}`, but not other
  params.
- Override params for one run, by name: `--param region=south` on the
  [command line](running.md#from-the-command-line), or
  `Pipeline.from_yaml(path, params={"region": "south"})` from Python.

To vary a value between runs without changing the file, give it an
environment variable with a default, as `region` does above.

## The run date

`${run_date}` is the day a run is for: today, unless you say otherwise.
Use it for the dated folders and files that daily loads read and write:

```yaml
steps:
  - id: events
    type: read
    connection: lake
    path: events/${run_date}/*.json       # events/2026-10-17/*.json

  - id: export
    type: write
    path: exports/events_${run_date}.csv
    inputs: {data: events}
```

For other layouts, such as `events/2026/10/17`, use a
[template](reading-writing/templates.md#dated-folders-and-files):
`path: events/{{ run_date.strftime('%Y/%m/%d') }}/*.json`.

To load another day, such as one that failed, set it when you run:

```bash
dagcraft configs/events.yaml --run-date 2026-10-16
```

```python
Pipeline.from_yaml("configs/events.yaml", run_date="2026-10-16")
```

- Inside text it's written as `2026-10-17`, like dates written in the file.
  As a whole value, such as a `python` step's argument or a query's param,
  it's a `datetime.date`.
- It's fixed when the pipeline loads, so every step of a run agrees on the
  day, even across midnight.
- Today is the date on the machine that runs the pipeline.
- Steps of your own get it as `context.run_date`.

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

## Your own modules

`imports` lists modules of yours to import before the rest of the file is
checked. Use it for modules that register operations, step types,
connections or formats, so the file can name them, with the `dagcraft`
command as well as from Python:

```python
# my_project/cleaning.py
from dagcraft import register_operation


@register_operation("strip_names", main="column")
def strip_names(data, column):
    return data.assign(**{column: data[column].str.strip()})
```

```yaml
pipeline:
  name: daily_sales
  imports:
    - my_project.cleaning

steps:
  - id: orders
    type: read
    path: data/orders.csv

  - id: clean
    type: transform
    inputs: {data: orders}
    operations:
      - strip_names: customer
```

- Write each module as you'd import it, `my_project.cleaning`, not as a
  file path.
- Modules are found in the folder you run from and in installed packages,
  as a `python` step's `callable` is.
- They're imported after the `env_file` loads, so they can use its
  variables.
- Functions named with `callable:` don't need listing: they're imported by
  name.

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
