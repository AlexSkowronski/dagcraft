# Running pipelines

## From Python

```python
from dagcraft import Pipeline, RunError, configure_logging

configure_logging()                                   # print progress

pipeline = Pipeline.from_yaml("configs/daily_sales.yaml")   # checks everything

try:
    result = pipeline.run()
except RunError as exc:
    print(exc)              # Pipeline 'daily_sales' failed at step 'orders': ...
    print(exc.result.steps) # every step's status, duration and error
    raise

result.output("big_orders")  # what a step returned
```

`run()` takes:

| Option | |
| --- | --- |
| `fail_fast` | Skip every remaining step after the first failure. Default `False`. |
| `run_id` | An ID for the run in logs and the result, e.g. your orchestrator's. Random by default. |
| `keep_outputs` | Keep every step's output on the result. Set `False` for big data, to free each output once no step needs it. |
| `max_workers` | How many independent steps run at once; overrides the file. |

The result has `success`, `duration`, `run_id`, `steps` (each with
`status`, `duration`, `attempts` and `error`) and `output(step_id)`.

A pipeline can be run any number of times; connections open and close for
each run.

### Where paths are relative to

Relative paths, the one you pass to `from_yaml` and those inside the file,
are relative to the folder you run from. The folder is fixed when the
pipeline loads. For a job that starts somewhere else, such as a scheduled
task, say where the project is:

```python
Pipeline.from_yaml(
    r"C:\jobs\my_project\configs\daily_sales.yaml",
    base_dir=r"C:\jobs\my_project",
)
```

## From the command line

```bash
dagcraft configs/daily_sales.yaml                      # check, then run
dagcraft configs/daily_sales.yaml --dry-run            # check and show the plan
dagcraft configs/daily_sales.yaml --check-connections  # check and sign in to each connection
```

`python -m dagcraft ...` does the same, where the `dagcraft` command isn't
on the PATH.

| Option | |
| --- | --- |
| `--dry-run` | Check the pipeline and show the steps it would run, in order. |
| `--check-connections` | Check the pipeline and prove each connection it uses works. |
| `--fail-fast` | Skip every remaining step after the first failure. |
| `--max-workers N` | Run up to N independent steps at once. |
| `--run-id ID` | An ID for the run in the logs. |
| `-v`, `--verbose` | Also log detail, such as each file and each SQL part read. |
| `--version` | Show dagcraft's version. |

| Exit status | |
| --- | --- |
| 0 | Success. |
| 1 | A step or a connection check failed. |
| 2 | The pipeline file or the options are invalid. |

## Checking connections

`--check-connections`, or `pipeline.check_connections()` from Python, opens
each connection the steps use and does one cheap real operation, without
running any steps:

| Connection | Check |
| --- | --- |
| `local` | The folder exists, or will be created when written to. |
| `azure_blob` | Lists the container, and whether the prefix has files. |
| `sharepoint` | Finds the site and library, and lists the folder. |
| `sql` | Runs `SELECT 1`. |
| `azure_sql` | Connects and shows the login and database. |

```
INFO    Checking 3 connection(s):
INFO      lake       azure_blob  OK      container 'raw' is reachable; prefix 'events' has files
ERROR     finance    sharepoint  FAILED  SharePoint returned 403 for GET https://graph.microsoft.com/...: Access denied.
INFO      warehouse  azure_sql   OK      connected to analytics as etl-app@contoso.com
ERROR   1 of 3 connection(s) failed.
```

## When a step fails

The steps that depend on it, directly or further down, are skipped, and the
other steps still run. Then `run()` raises `RunError`, naming every failed
step, with the first failure's exception chained so the traceback shows the
real cause.

For steps that can fail for a moment, such as reading over a network or
connecting to a database that's waking up, add retries:

```yaml
  - id: orders
    type: read
    connection: warehouse
    table: dbo.orders
    retries: 3          # waits 10s, 20s, then 40s
    retry_delay: 10
```

SQL writes run in a transaction, uploads replace the file in one go, and
local files are written under a temporary name first, so retrying a write is
safe.

Every error dagcraft raises is a `PipelineError`:

| Error | When |
| --- | --- |
| `ConfigError` | The pipeline file or the run's options are invalid. Raised when loading, before anything runs. |
| `ExecutionError` | A step or connection couldn't do its work. |
| `RunError` | `run()` had failed steps; `.result` has the details. |

## Running steps in parallel

Steps that don't depend on each other can run at the same time, which helps
when a pipeline runs several queries or downloads:

```yaml
pipeline:
  name: daily_sales
  max_workers: 4    # up to 4 independent steps at once; default 1
```

Steps still start in the order they're written, and each waits for its
inputs. With more than one worker, steps run in threads, so your own
functions should be safe to run alongside each other.

## Logging

Each step logs when it starts, what it produced and how long it took. Long
reads add progress lines, retries and skips are warnings, and failures are
errors with the traceback:

```
INFO    [daily_sales 4b554a3c] Starting run: 3 steps
INFO    [daily_sales 4b554a3c] orders: started: read orders/*.json from 'lake'
INFO    [daily_sales 4b554a3c] orders: found 12 files matching orders/*.json
INFO    [daily_sales 4b554a3c] orders: finished in 0.840s: a list of 12 items
WARNING [daily_sales 4b554a3c] report: skipped: upstream step 'totals' did not succeed
```

Every message names the pipeline, the run ID and the step, so runs can be
told apart in shared logs. The records also carry `pipeline`, `run_id` and
`step` attributes, for log handlers that store fields, such as Azure
Monitor.

dagcraft prints nothing until logging is set up. In a script,
`configure_logging()` prints dagcraft's messages with timestamps (other
libraries' only from WARNING up, since the Azure SDK logs every request).
In an application with its own logging, configure the `dagcraft` logger
instead; modules log under it by name, such as `dagcraft.readers.files`.

To time your own code, `Timer` works as a context manager or a decorator:

```python
import logging
from dagcraft import Timer

with Timer() as timer:
    pipeline.run()
print(f"{timer.elapsed:.1f}s")

@Timer("refresh", logger=logging.getLogger(__name__))   # logs "refresh took 1.234s"
def refresh(): ...
```
