# Steps and operations

Every step has these fields; each type adds its own.

| Field | |
| --- | --- |
| `id` | A name for the step, unique in the file. Other steps use it in `inputs`. |
| `type` | `read`, `write`, `transform` or `python`. |
| `inputs` | The steps whose outputs this one takes, as `name: step_id`. |
| `retries` | Run the step again this many times if it fails. Default 0. |
| `retry_delay` | Seconds before the first retry, doubling after each. Default 5. |

`inputs` decide the order: a step runs after every step it takes an input
from. Otherwise steps run in the order they're written.

## read

Fetches data through a connection. Takes no inputs.

```yaml
  - id: orders
    type: read
    connection: warehouse     # defaults to local
    table: sales.orders
```

The other fields depend on the connection: a `path` for
[files](reading-writing/files.md), a `query` or `table` for
[SQL](reading-writing/sql.md).

## write

Saves its input through a connection, and passes it on as its own output.

```yaml
  - id: save
    type: write
    connection: lake          # defaults to local
    path: clean/orders.parquet
    inputs:
      data: orders
```

Usually one input. Excel takes several, one sheet each. The other fields
depend on the connection, as for `read`.

## transform

Calls one of the built-in operations with its inputs and `args`:

```yaml
  - id: big_orders
    type: transform
    operation: filter
    inputs:
      data: orders
    args:
      expression: amount > 100
```

| Operation | Inputs | Args |
| --- | --- | --- |
| `filter` | `data` | `expression`: a [`DataFrame.query`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.query.html) expression, e.g. `amount > 100 and region == 'North'` |
| `select` | `data` | `columns`: the columns to keep, in order |
| `rename` | `data` | `columns`: old name to new name |
| `drop_nulls` | `data` | `subset`: optional columns to check; by default, any column |
| `sort` | `data` | `by`: a column or a list; `ascending` (default `true`) |
| `join` | `left`, `right` | `on`: shared column(s), plus any [`DataFrame.merge`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html) argument, such as `how: left` |
| `aggregate` | `data` | `by`: column(s) to group by; `columns`: column to `sum`, `mean`, `count`, `min`, `max`, ... |
| `flatten` | `data` (documents) | Turns documents into a table ([below](#flatten)) |

### flatten

Turns documents (dicts and lists, as JSON and YAML are read) into a table,
with [`pandas.json_normalize`](https://pandas.pydata.org/docs/reference/api/pandas.json_normalize.html).
Nested objects become dotted columns: `{"user": {"id": 1}}` gives a
`user.id` column.

```yaml
  - id: events
    type: transform
    operation: flatten
    inputs:
      data: batch        # {"batch_id": "b1", "events": [{...}, {...}]}
    args:
      record_path: events      # one row per item in "events"
      meta: [batch_id]         # copied onto each row
```

| Arg | |
| --- | --- |
| `record_path` | The list inside each document to take rows from. Without it, each document (or each item of a list) is a row. |
| `meta` | Document fields to copy onto each row; nested ones as a list, e.g. `[source, system]`. |
| `max_level` | How many levels of nesting to flatten; deeper objects stay as dicts. |
| `sep` | The separator in column names. Default `.`. |

## python

Calls a function of your own with its inputs and `args`, as keyword
arguments:

```yaml
  - id: summary
    type: python
    callable: my_functions:summarise    # module:function
    inputs:
      data: batch
    args:
      top: 10
```

```python
# my_functions.py, in the folder you run from
def summarise(data, top):
    ...
    return result     # a DataFrame, a dict, a list: whatever the next step needs
```

Modules in the folder you run from can be imported, as can any installed
package. See [Your own Python functions](recipes/python-functions.md).

!!! warning "Only run pipeline files you trust"
    A pipeline file can run code: `python` steps call functions and
    `filter` expressions are evaluated by pandas. Treat pipeline files like
    any other code.
