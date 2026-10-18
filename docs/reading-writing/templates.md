# Templates

The fields that say *what* a step reads or writes can be
[Jinja](https://jinja.palletsprojects.com/) templates. Build a query, a
table name or a path with logic, dates and your own functions:

| Field | Steps |
| --- | --- |
| `path` | File reads and writes. |
| `query`, `table` | SQL reads; `table` for SQL writes too. |
| `query_file` | SQL reads: the file's contents, not its name. |

Everything else in the file is left as written.

## Dated folders and files

```yaml
  - id: events
    type: read
    connection: lake
    path: events/{{ run_date.strftime('%Y/%m/%d') }}/*.json   # events/2026/10/17/*.json

  - id: export
    type: write
    connection: sharepoint
    path: "{{ run_date.strftime('%Y-%m') }}/orders.xlsx"      # 2026-10/orders.xlsx
    inputs:
      data: orders
```

`run_date` is [the run date](../pipeline-file.md#the-run-date), a
`datetime.date`, so `strftime`, `.year` and arithmetic work:
`{{ run_date - timedelta(days=1) }}` is the day before.

YAML reads a value that starts with `{` as a mapping, so put quotes around
values that start with `{{`, as `export`'s path has.

## SQL

```sql
-- sql/orders.sql
SELECT order_id, {{ params.columns | join(', ') }}
FROM {{ params.schema }}.orders
WHERE order_date >= :since
{% if params.region %}
  AND region = :region
{% endif %}
```

```yaml
params:
  schema: sales
  columns: [customer_id, amount]
  region: ""                      # set with --param region=north

steps:
  - id: orders
    type: read
    connection: warehouse
    query_file: sql/orders.sql
    params:
      since: ${run_date}
      region: ${params.region}
```

Use the template for the query's shape: which columns, which table, which
filters. Use `:name` placeholders for values: values in `params` are sent
to the database separately from the SQL, never pasted into it. A filter
the template leaves out just doesn't use its value.

## What templates can use

| Name | |
| --- | --- |
| `params` | The pipeline's params: `{{ params.region }}`. |
| `run_date` | The day the run is for, a `datetime.date`. |
| `timedelta` | For date arithmetic: `{{ run_date - timedelta(days=7) }}`. |
| `env` | Environment variables: `{{ env.REGION }}`, or `{{ env.get('REGION', 'north') }}` with a default. |
| Your functions | Registered with `template_function`; see [below](#your-own-functions). |

Plus everything Jinja has, such as `{% if %}`, `{% for %}` and filters like
`join`, `upper` and `default`.

## Your own functions

```python
# my_project/dates.py
from datetime import timedelta

from dagcraft import template_function


@template_function
def last_business_day(day):
    day -= timedelta(days=1)
    while day.weekday() >= 5:     # Saturday or Sunday
        day -= timedelta(days=1)
    return day
```

```yaml
pipeline:
  name: daily_sales
  imports: [my_project.dates]

steps:
  - id: sales
    type: read
    connection: lake
    path: sales/{{ last_business_day(run_date) }}/*.csv
```

A function is called by its name. List its module in
[`imports`](../pipeline-file.md#your-own-modules) so it's registered before
the rest of the file is checked.

## Checked when it loads

Templates are rendered when the pipeline loads, so:

- A [dry run](../running.md#from-the-command-line) shows paths, tables and
  queries as they were rendered: `read events/2026/10/17/*.json from
  'lake'`. With `-v`, it logs each rendered query file too.
- A misspelt name is an error, not blank text, and says where:

```
ConfigError: Step 'events': in path: 'dict object' has no attribute 'regin'
```

## `${...}` or `{{ ... }}`?

- `${params.NAME}`, `${env:NAME}` and `${run_date}` work anywhere in the
  file, and put in a value as it is.
- `{{ ... }}` and `{% ... %}` work in the fields above, and can compute:
  lay out a date, leave out a filter, call your function.

For a value as it is, `${...}` is shorter. Reach for a template when you
need logic.
