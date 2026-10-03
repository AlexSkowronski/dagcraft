# dagcraft

Config-driven data pipelines for Python. You describe the steps in a YAML
file (read data, transform it, write it somewhere) and dagcraft checks the
whole file, works out the order, and runs it.

```python
from dagcraft import Pipeline

Pipeline.from_yaml("configs/daily_sales.yaml").run()
```

```yaml
pipeline:
  name: daily_sales

connections:
  lake:
    type: azure_blob
    account: mystorageaccount     # signs in as your `az login`
    container: raw

steps:
  - id: orders
    type: read
    connection: lake
    path: orders/2026-10-02.parquet

  - id: big_orders
    type: transform
    operation: filter
    inputs: {data: orders}
    args: {expression: "amount > 100"}

  - id: save
    type: write
    path: output/big_orders.csv     # the built-in local connection
    inputs: {data: big_orders}
```

## What it can do

| | Built in |
| --- | --- |
| **[Connections](connections/local.md)**: where data lives, and signing in | Local files, Azure Blob Storage, SharePoint, any SQL database, Azure SQL |
| **[Formats](reading-writing/files.md)**: how files become data | Tables: CSV, Parquet, Excel. Documents (dicts and lists): JSON, JSON Lines, YAML |
| **[Steps](steps.md)**: what a pipeline does | `read`, `write`, `transform` (built-in operations), `python` (your own functions) |
| **[Running](running.md)** | From Python or the `dagcraft` command; dry runs, connection checks, retries, parallel steps, logs per step |

## How it works

1. **Load:** `Pipeline.from_yaml` reads the file and checks everything that
   can be checked without running: every field, every connection, that the
   steps form a graph. A pipeline that loads is one that can run.
2. **Plan:** a step runs once the steps it takes `inputs` from have
   finished; otherwise steps run in the order they're written.
3. **Run:** each step's output is passed to the steps that use it.
   Connections open the first time they're needed and close at the end.

## Where next

- New to dagcraft? Start with **[Getting started](getting-started.md)**.
- Moving data from Azure? See the **[recipes](recipes/blob-json-to-sql.md)**.
- Looking something up? Every field is listed on the page for its
  connection, format or step.
