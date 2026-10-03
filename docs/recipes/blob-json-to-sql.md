# Blob JSON into Azure SQL

Every day, JSON files land in a blob container. This pipeline reads a day's
files, parses them with your own function, and loads the result into an
Azure SQL table, safely re-runnable.

```
my_project/
  .env
  configs/events_to_sql.yaml
  my_functions.py
```

## Settings

```
# .env
STORAGE_ACCOUNT=mystorageaccount
SQL_SERVER=myserver.database.windows.net
SQL_DATABASE=analytics
```

## The pipeline

```yaml
# configs/events_to_sql.yaml
pipeline:
  name: events_to_sql
  env_file: .env

params:
  run_date: ${env:RUN_DATE:-2026-10-02}    # set RUN_DATE to load another day

connections:
  lake:
    type: azure_blob
    account: ${env:STORAGE_ACCOUNT}
    container: raw
    prefix: events
  warehouse:
    type: azure_sql
    server: ${env:SQL_SERVER}
    database: ${env:SQL_DATABASE}

steps:
  # The day's files, as a list of documents; each gets a source_file key.
  - id: batches
    type: read
    connection: lake
    path: ${params.run_date}/*.json
    source_column: source_file
    retries: 2

  # Your function turns the documents into a table.
  - id: purchases
    type: python
    callable: my_functions:purchases
    inputs:
      batches: batches

  # Re-running a day replaces its rows instead of duplicating them.
  - id: load
    type: write
    connection: warehouse
    table: staging.purchases
    if_exists: upsert
    keys: [event_id]
    inputs:
      data: purchases
```

## Your function

```python
# my_functions.py
import pandas as pd


def purchases(batches):
    """One row per purchase event, from a day's batch documents."""
    rows = [
        {
            "event_id": event["event_id"],
            "user_id": event["user"]["id"],
            "product_id": event["properties"]["product_id"],
            "batch_id": batch["batch_id"],
            "source_file": batch["source_file"],
        }
        for batch in batches
        for event in batch["events"]
        if event["type"] == "purchase"
    ]
    return pd.DataFrame(rows)
```

If the documents only need flattening, a transform with a `flatten`
operation does it without any Python; see [Documents](../steps.md#documents).

## Run it

```bash
dagcraft configs/events_to_sql.yaml --check-connections   # first time: prove sign-in works
dagcraft configs/events_to_sql.yaml
```

The identity you run as needs *Storage Blob Data Reader* on the storage
account, and a database user that can read, write and create tables in the
`staging` schema (for the upsert's staging table).

## On a schedule

Start the job in the project folder, or pass `base_dir` from Python:

```python
from dagcraft import Pipeline, configure_logging

configure_logging()
Pipeline.from_yaml(
    r"C:\jobs\my_project\configs\events_to_sql.yaml",
    base_dir=r"C:\jobs\my_project",
).run(keep_outputs=False)
```
