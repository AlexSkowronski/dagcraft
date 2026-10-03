# dagcraft

[![CI](https://github.com/AlexSkowronski/dagcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/AlexSkowronski/dagcraft/actions/workflows/ci.yml)
[![Docs](https://github.com/AlexSkowronski/dagcraft/actions/workflows/docs.yml/badge.svg)](https://alexskowronski.github.io/dagcraft/)

Config-driven data pipelines for Python. Describe the steps in YAML (read
data, transform it, write it somewhere) and run them with one line.

**[Read the guide →](https://alexskowronski.github.io/dagcraft/)**

## Install

```bash
pip install "dagcraft-pipelines[all]"
```

It's `dagcraft-pipelines` on PyPI; you import and run it as `dagcraft`. See
[installing only what you need](https://alexskowronski.github.io/dagcraft/getting-started/#install).

## Example

`configs/daily_sales.yaml`:

```yaml
pipeline:
  name: daily_sales

connections:
  lake:
    type: azure_blob
    account: mystorageaccount     # signs in as your `az login`
    container: raw
  warehouse:
    type: azure_sql
    server: myserver.database.windows.net
    database: analytics

steps:
  - id: orders
    type: read
    connection: lake
    path: orders/2026-10-02.parquet

  - id: big_orders
    type: transform                 # a chain of operations, top to bottom
    inputs: {data: orders}
    operations:
      - drop_nulls: [customer_id]
      - filter: amount > 100
      - derive: {total: price * quantity}
      - check: {unique: [order_id]}

  - id: load
    type: write
    connection: warehouse
    table: sales.big_orders
    if_exists: upsert             # safe to re-run
    keys: [order_id]
    inputs: {data: big_orders}
```

Run it from Python:

```python
from dagcraft import Pipeline

Pipeline.from_yaml("configs/daily_sales.yaml").run()
```

or from the command line:

```bash
dagcraft configs/daily_sales.yaml --dry-run   # check it, show the steps
dagcraft configs/daily_sales.yaml             # run it
```

## What it can do

| | |
| --- | --- |
| [Connections](https://alexskowronski.github.io/dagcraft/connections/local/) | Local files, Azure Blob Storage, SharePoint, any SQL database, Azure SQL. Sign in with `az login`, a managed identity or a connection string. |
| [Formats](https://alexskowronski.github.io/dagcraft/reading-writing/files/) | CSV, Parquet and Excel as tables; JSON, JSON Lines and YAML as plain dicts and lists. Many files at once with wildcards. |
| [SQL](https://alexskowronski.github.io/dagcraft/reading-writing/sql/) | `.sql` files with parameters, parallel reads of big tables, transactional writes and upserts. |
| [Transforms](https://alexskowronski.github.io/dagcraft/steps/#transform) | A whole stage of cleaning in one step: filter, join, derive, cast, dedupe, aggregate, flatten, data checks, and [your own Python functions](https://alexskowronski.github.io/dagcraft/recipes/python-functions/). |
| [Running](https://alexskowronski.github.io/dagcraft/running/) | Everything checked before it runs, connection checks, retries, parallel steps, and a log line per step. |

## Learn more

- [Getting started](https://alexskowronski.github.io/dagcraft/getting-started/)
- [Recipes](https://alexskowronski.github.io/dagcraft/recipes/blob-json-to-sql/): Blob JSON into Azure SQL, a SharePoint Excel report
- [Changelog](https://github.com/AlexSkowronski/dagcraft/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/AlexSkowronski/dagcraft/blob/main/CONTRIBUTING.md)

dagcraft is in early development (0.1); the pipeline format may still
change. MIT licensed.
