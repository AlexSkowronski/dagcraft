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

Applies a list of operations to a table, top to bottom: each works on the
result of the one before, and the step's output is the last result. One
transform holds a whole stage of work, such as "clean the orders", up to the
point where the data goes somewhere else.

```yaml
  - id: clean_orders
    type: transform
    inputs:
      data: orders              # the table the operations start from
      customers: customers      # other inputs, for joins
    operations:
      - drop_nulls: [customer_id]
      - derive:
          total: price * quantity
      - filter: total > 100
      - join: {right: customers, on: customer_id, how: left}
      - rename: {cust_name: customer}
      - select: [order_id, customer, total]
      - check: {not_null: [customer], unique: [order_id]}
```

| Field | |
| --- | --- |
| `inputs` | Must include `data`, where the operations start. Other inputs are named in operations that take a table, such as `join`'s `right`. |
| `operations` | The operations, in order. |

Each operation is written one of three ways:

| Form | Example | Means |
| --- | --- | --- |
| `name: value` | `filter: total > 100` | The value fills the operation's main option (in **bold** below). |
| `name: {options}` | `sort: {by: total, ascending: false}` | Each option by name. |
| `name` | `drop_nulls` | No options. |

Every operation's options are checked when the pipeline loads, so a typo
fails before anything runs. With `-v`, each operation logs its effect
(`filter: 10,000 rows x 6 columns -> 4,120 rows x 6 columns`), and a failure
names the operation: `operation 4 (join) failed: ...`.

### Rows

| Operation | Options |
| --- | --- |
| `filter` | **`expression`**: the rows to keep, as for [`DataFrame.query`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.query.html): `total > 100 and region == 'North'`. Backticks around column names with spaces. |
| `drop_nulls` | **`subset`**: drop rows with a missing value in these columns; without it, in any column. |
| `dedupe` | **`subset`**: drop rows repeating these columns (or every column); `keep`: `first` (default) or `last`. |
| `sort` | **`by`**: a column or a list; `ascending`: `true` (default), `false`, or one per column. |

### Columns

| Operation | Options |
| --- | --- |
| `select` | **`columns`**: keep these, in this order. |
| `drop` | **`columns`**: remove these. |
| `rename` | `old name: new name` pairs. |
| `cast` | `column: type` pairs. Types: `int`, `float`, `str`, `bool`, `datetime`, or a pandas type such as `category`. |
| `derive` | `column: expression` pairs, as for [`DataFrame.eval`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.eval.html): `total: price * quantity`. Each can use the ones before it. |
| `fill_nulls` | `column: value` pairs. |

### Combining

| Operation | Options |
| --- | --- |
| `join` | `right`: another input of the step; `on`: shared column(s); `how`: `inner` (default), `left`, `right` or `outer`; plus any [`DataFrame.merge`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html) option, such as `suffixes`. |
| `aggregate` | `by`: column(s) to group by; `columns`: `column: function` pairs, with `sum`, `mean`, `count`, `min`, `max`, ... |

### Checking

`check` passes the table on unchanged if it looks right, and otherwise fails
the step, listing every problem it found:

```yaml
      - check:
          columns: [order_id, total]        # these exist
          not_null: [order_id, customer]    # no missing values
          unique: [order_id]                # together, identify each row
          accepted: {status: [open, shipped, closed]}
          min_rows: 1
          max_rows: 1000000
```

```
operation 7 (check) failed: customer has 3 missing values; 2 rows share order_id with another row, such as order_id=1041
```

Add `warn: true` to log the problems as a warning and carry on instead.

### Documents

`flatten` turns documents (dicts and lists, as JSON and YAML are read) into
a table, with [`pandas.json_normalize`](https://pandas.pydata.org/docs/reference/api/pandas.json_normalize.html).
Nested objects become dotted columns: `{"user": {"id": 1}}` gives a
`user.id` column. It's usually first, followed by table operations:

```yaml
  - id: purchases
    type: transform
    inputs:
      data: batch               # {"batch_id": "b1", "events": [{...}, {...}]}
    operations:
      - flatten:
          record_path: events   # one row per item in "events"
          meta: [batch_id]      # copied onto each row
      - filter: type == 'purchase'
      - rename: {user.id: user_id}
```

| Option | |
| --- | --- |
| `record_path` | The list inside each document to take rows from. Without it, each document (or each item of a list) is a row. |
| `meta` | Document fields to copy onto each row; nested ones as a list, e.g. `[source, system]`. |
| `max_level` | How many levels of nesting to flatten; deeper objects stay as dicts. |
| `sep` | The separator in column names. Default `.`. |

### Your own code

`python` calls a function of yours on the current table, as one operation of
the chain:

```yaml
    operations:
      - drop_nulls
      - python: my_functions:fix_codes                       # main option: callable
      - python: {callable: my_functions:bucket, size: 10}    # with arguments
      - select: [order_id, code, bucket]
```

```python
# my_functions.py
def fix_codes(data):
    return data.assign(code=data["code"].str.upper())

def bucket(data, size):
    return data.assign(bucket=data["total"] // size)
```

The function gets the table first, then any other options by name, and
returns the table for the next operation. For a whole step of your own
code, with several inputs, use a [`python` step](#python) instead.

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
