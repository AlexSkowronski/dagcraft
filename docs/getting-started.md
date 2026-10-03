# Getting started

## Install

dagcraft needs Python 3.11 or newer. It's called `dagcraft-pipelines` on
PyPI; you import and run it as `dagcraft`.

```bash
pip install "dagcraft-pipelines[all]"
```

Or install only what you use:

| Command | Adds |
| --- | --- |
| `pip install dagcraft-pipelines` | Local files: CSV, Parquet, JSON, JSON Lines, YAML |
| `pip install "dagcraft-pipelines[excel]"` | Excel workbooks |
| `pip install "dagcraft-pipelines[sql]"` | SQL databases |
| `pip install "dagcraft-pipelines[azure]"` | Azure Blob Storage, Azure SQL and SharePoint |

If you use a missing feature, the error names the extra to install.

### For Azure

- **Signing in:** run `az login` (the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)).
  dagcraft signs in as you; in Azure it uses the managed identity instead.
- **Azure SQL** also needs Microsoft's
  [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).

## A project

A typical layout keeps pipelines in a folder of their own, and is run from
the project's root:

```
my_project/
  .env                    # settings and secrets, not committed
  connections.yaml        # connections the pipelines share
  configs/
    daily_sales.yaml      # the pipeline
  sql/
    orders.sql            # queries the pipeline runs
  my_functions.py         # your own Python, for python steps
  main.py
```

Pipelines `include: [connections.yaml]` instead of repeating the same
connections; see [Sharing connections](pipeline-file.md#sharing-connections).

!!! tip "Paths are relative to where you run"
    Every relative path, both the one you pass to `from_yaml` and the ones
    inside the file (`env_file`, `query_file`, a local connection's `root`),
    is relative to the folder you run from: here, `my_project/`. So the
    pipeline says `query_file: sql/orders.sql`, not `../sql/orders.sql`.
    For a job that starts elsewhere, pass `base_dir`; see
    [Running pipelines](running.md#where-paths-are-relative-to).

## A first pipeline

`configs/daily_sales.yaml` reads a CSV, cleans it up, and writes the big
orders out:

```yaml
pipeline:
  name: daily_sales

steps:
  - id: orders
    type: read
    path: data/orders.csv

  - id: big_orders
    type: transform
    inputs:
      data: orders          # this step's input "data" is the output of "orders"
    operations:             # applied in order, each to the last one's result
      - drop_nulls: [customer_id]
      - filter: amount > 100
      - sort: {by: amount, ascending: false}

  - id: save
    type: write
    path: output/big_orders.csv
    inputs:
      data: big_orders
```

Each step has an `id` and a `type`. `inputs` connect the steps: the order
they run in follows from them. A `transform` holds a whole list of
operations, so one step can do all the cleaning a table needs; see
[Steps and operations](steps.md#transform).

## Run it

=== "Python"

    ```python
    from dagcraft import Pipeline, configure_logging

    configure_logging()   # show progress in the console

    result = Pipeline.from_yaml("configs/daily_sales.yaml").run()
    result.output("big_orders")   # a step's output: here, a DataFrame
    ```

=== "Command line"

    ```bash
    dagcraft configs/daily_sales.yaml
    ```

    If the `dagcraft` command isn't found, `python -m dagcraft` does the
    same.

Each step logs what it did:

```
INFO    [daily_sales 4b554a3c] Starting run: 3 steps
INFO    [daily_sales 4b554a3c] orders: started: read data/orders.csv from 'local'
INFO    [daily_sales 4b554a3c] orders: finished in 0.008s: 120 rows x 5 columns
INFO    [daily_sales 4b554a3c] big_orders: started: transform: drop_nulls -> filter -> sort
INFO    [daily_sales 4b554a3c] big_orders: finished in 0.003s: 41 rows x 5 columns
...
INFO    [daily_sales 4b554a3c] Run succeeded in 0.021s
```

## Check before you run

```bash
dagcraft configs/daily_sales.yaml --dry-run            # show the steps, run nothing
dagcraft configs/daily_sales.yaml --check-connections  # sign in to each connection
```

`--check-connections` does one cheap real operation per connection (lists
a folder, runs `SELECT 1`), so credentials, permissions and drivers are
proven in seconds. For Azure SQL it also shows who you signed in as.

## Next

- [The pipeline file](pipeline-file.md): params, `.env` files and secrets.
- [Connections](connections/local.md): reading from Azure, SharePoint and SQL.
- [Your own Python functions](recipes/python-functions.md).
