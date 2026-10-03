# SQL and Azure SQL

Two connection types reach SQL databases. Both read and write the same way;
they differ in how they connect.

| Type | For | Needs |
| --- | --- | --- |
| `azure_sql` | Azure SQL Database and SQL Server, signing in with your identity or a connection string | `pip install "dagcraft-pipelines[azure]"` and Microsoft's [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| `sql` | Any database SQLAlchemy supports, by URL: SQLite, Postgres, MySQL, ... | `pip install "dagcraft-pipelines[sql]"` plus a driver for the database (SQLite needs none) |

## Azure SQL

```yaml
connections:
  warehouse:
    type: azure_sql
    server: myserver.database.windows.net
    database: analytics
```

| Field | |
| --- | --- |
| `server` | The server, e.g. `myserver.database.windows.net` (port 1433 unless you write `server,port`). |
| `database` | The database. |
| `driver` | The ODBC driver. Defaults to `ODBC Driver 18 for SQL Server`. |
| `connection_string` | Or a full ODBC connection string, instead of `server` and `database`. |

=== "Your identity (server and database)"

    dagcraft signs in with an Entra ID token from `DefaultAzureCredential`:
    your `az login` locally, a managed identity in Azure, or a service
    principal's environment variables. A fresh token is fetched for each
    database connection, so long runs aren't cut off when one expires.

    The identity needs a user in the database, for example:

    ```sql
    CREATE USER [you@contoso.com] FROM EXTERNAL PROVIDER;
    ALTER ROLE db_datareader ADD MEMBER [you@contoso.com];
    ALTER ROLE db_datawriter ADD MEMBER [you@contoso.com];
    ```

=== "Connection string"

    ```yaml
    warehouse:
      type: azure_sql
      connection_string: ${env:AZURE_SQL_CONNECTION}
    ```

    ```
    # .env
    AZURE_SQL_CONNECTION='Driver={ODBC Driver 18 for SQL Server};Server=tcp:myserver.database.windows.net,1433;Database=analytics;Uid=etl_user;Pwd=...;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
    ```

    It must be the **ODBC** form, with `Driver={...}`: in the Azure portal,
    the database's *Connection strings* page has an ODBC tab. The ADO.NET
    form (`Initial Catalog=...`) won't work. The string is used as it is,
    for example with SQL authentication, and never appears in logs.

Writes use pyodbc's `fast_executemany`, so loading large tables is quick.

`--check-connections` connects and shows which login and database it got:
handy when `DefaultAzureCredential` might pick an identity you didn't
expect.

## Any database by URL

```yaml
connections:
  local_db:
    type: sql
    url: sqlite:///data/warehouse.db          # relative to the folder you run from
  postgres:
    type: sql
    url: ${env:POSTGRES_URL}                   # postgresql+psycopg://user:pass@host/db
```

| Field | |
| --- | --- |
| `url` | A [SQLAlchemy database URL](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls). Write ones with passwords as `${env:NAME}`. |

A SQLite file's folder is created if it's missing.

## Reading and writing

Both types take the same step fields: a `query`, `query_file` or `table` to
read; a `table` and `if_exists` to write. See [SQL](../reading-writing/sql.md).
