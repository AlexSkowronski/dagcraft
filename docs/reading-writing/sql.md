# SQL

Read and write steps on [SQL connections](../connections/sql.md) (`sql` and
`azure_sql`) take a query or a table instead of a path.

## Reading

Set one of `query`, `query_file` or `table`:

=== "A .sql file"

    ```yaml
      - id: actuals
        type: read
        connection: warehouse
        query_file: sql/actuals_by_department.sql   # relative to where you run
        params:
          year: 2026
    ```

    ```sql
    -- sql/actuals_by_department.sql: spend per department for :year
    SELECT department, SUM(amount) AS actual
    FROM finance.ledger
    WHERE YEAR(posted_on) = :year
    GROUP BY department
    ```

=== "An inline query"

    ```yaml
      - id: open_orders
        type: read
        connection: warehouse
        query: SELECT * FROM sales.orders WHERE status = :status
        params:
          status: open
    ```

=== "A whole table"

    ```yaml
      - id: customers
        type: read
        connection: warehouse
        table: dbo.customers
    ```

| Field | |
| --- | --- |
| `query` | SQL to run. Use `:name` placeholders for values. |
| `query_file` | Or a `.sql` file, relative to the folder you run from. Same placeholders. |
| `table` | Or a whole table, as `name` or `schema.name`. |
| `params` | Values for the placeholders. They're sent separately from the SQL, never pasted into it. |
| `args` | Passed to `pandas.read_sql`, e.g. `{parse_dates: [posted_on]}`. |
| `partition` | Read a large table in parallel parts ([below](#large-reads-in-parallel-parts)). |

Only `:name` in SQL code is a placeholder; inside `-- comments` and
`'strings'` it's left alone, so a `.sql` file can describe its parameters.

### Large reads in parallel parts

`partition` splits a big read into ranges of a whole-number column, such as
an ID, reads them at the same time on separate connections, and combines
them. It's typically a few times faster on a large table, if the database
has the capacity.

```yaml
  - id: orders
    type: read
    connection: warehouse
    table: dbo.orders
    partition:
      column: order_id   # its MIN and MAX set the range
      parts: 8           # 2 to 32
```

Rows where the column is NULL are read too. Set `lower` and `upper` to read
only that range, instead of finding it with MIN and MAX.

For a query, put `:partition_start` and `:partition_end` where the range
belongs, and give the bounds. dagcraft never rewrites your SQL, so this
works with CTEs and anything else:

```yaml
    query_file: sql/orders.sql   # ... WHERE o.order_id BETWEEN :partition_start AND :partition_end
    partition:
      parts: 8
      lower: 1
      upper: 50000000
```

## Writing

```yaml
  - id: save
    type: write
    connection: warehouse
    table: staging.orders
    if_exists: append
    inputs:
      data: orders
```

| Field | |
| --- | --- |
| `table` | `name` or `schema.name`. |
| `if_exists` | What to do if the table exists: `fail` (the default), `append`, `delete_rows` (empty it, keeping its definition), `replace` (drop and recreate it) or `upsert` ([below](#upserts-safe-to-re-run)). A missing table is always created. |
| `keys` | For `upsert`: the columns that identify a row. |
| `args` | Passed to `DataFrame.to_sql`, e.g. `dtype` or `chunksize`. |

Each write runs in one transaction, so a failure part-way leaves the table
as it was. The data must be a table; to write [documents](files.md#documents-into-a-table),
`flatten` them first.

### Upserts: safe to re-run

`if_exists: upsert` replaces the rows whose `keys` match and adds the rest,
so loading the same day twice doesn't duplicate it:

```yaml
  - id: load
    type: write
    connection: warehouse
    table: staging.purchases
    if_exists: upsert
    keys: [event_id]          # several columns for a composite key
    inputs:
      data: purchases
```

How it works: the rows are loaded into a staging table next to the target,
the target's rows with matching keys are deleted, and the staged rows are
inserted, all in one transaction. It's plain SQL, so it works on every
database and needs no unique constraint, though an index on the keys keeps
it fast.

- The identity needs permission to create tables in the target's schema, for
  the staging table, which is always dropped afterwards.
- Before writing, dagcraft checks that every row has all its keys, that no
  two rows share them, and that the table has every column of the data.
- Matching rows are replaced whole: columns the data doesn't have are reset
  to their defaults, and an identity column can't be in the data.
