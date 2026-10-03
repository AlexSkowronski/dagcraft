# Your own Python functions

A `python` step calls any function you write, so the pipeline file handles
the reading, writing and order, and your code handles the logic.

```yaml
  - id: cleaned
    type: python
    callable: my_functions:clean_orders
    inputs:
      orders: raw_orders        # the output of step raw_orders
      customers: customers
    args:
      min_amount: 10
```

```python
# my_functions.py
def clean_orders(orders, customers, min_amount):
    big = orders[orders["amount"] >= min_amount]
    return big.merge(customers, on="customer_id")
```

## How it's called

- **Inputs** arrive as keyword arguments, named as in `inputs`; **args** are
  added the same way. A name can't be in both.
- **What you get** is whatever the input step produced: a DataFrame from
  CSV, Parquet, Excel or SQL; dicts and lists from JSON, JSON Lines or YAML.
- **What you return** is the step's output, passed to the steps that use
  it: a DataFrame to write a table or to SQL, a dict or a list to write
  JSON or YAML.

## Where your code lives

`callable` is `module:function`. The module can be:

- A file in the folder you run from: `my_functions.py` is
  `my_functions:clean_orders`.
- A package in it: `my_project/transforms/orders.py` is
  `my_project.transforms.orders:clean_orders`.
- Any installed package.

The pipeline checks the function exists when it loads, so a typo shows up
before anything runs.

## Logging from your function

Log with `dagcraft.get_logger` and your messages name the run and step, like
dagcraft's own:

```python
from dagcraft import get_logger

logger = get_logger(__name__)


def clean_orders(orders, customers, min_amount):
    logger.info("dropping %d small orders", (orders["amount"] < min_amount).sum())
    ...
```

```
INFO    [daily_sales 4b554a3c] cleaned: dropping 12 small orders
```

## Testing your function

It's a plain function, so test it directly, without a pipeline:

```python
import pandas as pd
from my_functions import clean_orders


def test_small_orders_are_dropped():
    orders = pd.DataFrame({"customer_id": [1, 1], "amount": [5, 50]})
    customers = pd.DataFrame({"customer_id": [1], "name": ["Ada"]})

    result = clean_orders(orders, customers, min_amount=10)

    assert result["amount"].tolist() == [50]
```

## Inside a transform

When your function is one part of a stage of cleaning, call it as a
`python` operation in a transform's list instead of a step of its own. It
gets the current table first and returns the next one:

```yaml
  - id: clean_orders
    type: transform
    inputs:
      data: orders
    operations:
      - drop_nulls: [customer_id]
      - python: my_functions:fix_codes                     # fix_codes(data)
      - python: {callable: my_functions:bucket, size: 10}  # bucket(data, size=10)
      - check: {not_null: [code]}
```

Use a `python` step for code that takes several inputs.

## Reusable operations

For a function you'll use across pipelines with different settings,
register it as an operation and use it in `transform` steps; see
[Extending dagcraft](../extending.md#operations).
