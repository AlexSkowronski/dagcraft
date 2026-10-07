# Check your SQL Server

Before trusting dagcraft with a real load, check it against your own
database: your server, your permissions, your ODBC driver. This pipeline
writes a small table, upserts into it, reads it back in parallel parts and
with a query parameter, then checks every result with `check` operations.
If anything's off, the run fails and says what.

It's in the repository as
[`config/checks/sql_server`](https://github.com/AlexSkowronski/dagcraft/tree/main/config/checks/sql_server).

## Run it

1. Copy the folder's files (below) into a folder on your machine.
2. Copy `.env.example` to `.env` and set your server and database.
3. From that folder:

    ```bash
    az login                    # if you sign in as yourself
    dagcraft pipeline.yaml
    ```

A run that succeeds ends with `SUCCESS`: writes, upserts, partitioned reads
and query parameters all work on your database. Afterwards, drop the table
it made:

```sql
DROP TABLE dagcraft_check_orders;
```

!!! note "What it needs"
    Permission to create, drop and write tables, in the default schema or
    the one `CHECK_TABLE` names: the upsert creates a staging table beside
    the target. A failure such as `CREATE TABLE permission denied` says
    which permission is missing.

## If it fails

The summary shows which step failed, and its error says why:

| Failing step | Means |
| --- | --- |
| `write_seed` | Can't create or write tables: check permissions, the driver, the server name. |
| `upsert` | Can't create the staging table, or the upsert's SQL failed. |
| `read_back` | Partitioned reads failed. |
| `big_orders` | A query with a `:parameter` failed, or found nothing: the upsert didn't change order 3. |
| `check_table` | The table came back wrong: the error lists what the checks found. |

## The files

`pipeline.yaml`:

```yaml
--8<-- "config/checks/sql_server/pipeline.yaml"
```

`connections.yaml`:

```yaml
--8<-- "config/checks/sql_server/connections.yaml"
```

`.env.example`:

```
--8<-- "config/checks/sql_server/.env.example"
```

`seed.csv`:

```
--8<-- "config/checks/sql_server/seed.csv"
```

`changes.csv`:

```
--8<-- "config/checks/sql_server/changes.csv"
```
