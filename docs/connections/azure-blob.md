# Azure Blob Storage

Files in a Blob Storage container, including ADLS Gen2 accounts. Needs
`pip install "dagcraft-pipelines[azure]"`.

```yaml
connections:
  lake:
    type: azure_blob
    account: mystorageaccount
    container: raw
    prefix: events               # optional folder inside the container

steps:
  - id: events
    type: read
    connection: lake
    path: 2026-10-02/*.json      # raw/events/2026-10-02/*.json
```

| Field | |
| --- | --- |
| `container` | The container. |
| `prefix` | Optional folder inside the container; step paths are relative to it. |
| `account` | The storage account, to sign in with your identity (below). |
| `connection_string` | Or a connection string, usually `${env:NAME}`. |

Set exactly one of `account` or `connection_string`.

## Signing in

=== "Your identity (account)"

    ```yaml
    lake:
      type: azure_blob
      account: mystorageaccount
      container: raw
    ```

    dagcraft uses `DefaultAzureCredential`, which tries, in turn: service
    principal environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
    `AZURE_CLIENT_SECRET`), a managed identity when running in Azure, and
    your `az login`. The identity needs a data role on the account, such as
    *Storage Blob Data Contributor* (or *Reader* to only read).

=== "Connection string"

    ```yaml
    lake:
      type: azure_blob
      connection_string: ${env:LAKE_CONNECTION_STRING}
      container: raw
    ```

    Copy it from the storage account's *Access keys* page in the Azure
    portal, and keep it in an [environment variable or `.env`
    file](../pipeline-file.md#env-files). It never appears in logs.

!!! note "AZURE_STORAGE_CONNECTION_STRING"
    If that environment variable is set, a connection with `account`
    refuses to sign in: the library underneath (adlfs) would quietly use
    the variable's connection string instead, possibly for another account.
    Unset it, or use `connection_string` to choose one.

## Checking

`--check-connections` lists the container (which fails on bad credentials
or permissions) and says whether the prefix has files yet.

For the fields a read or write step takes, see [Files and
formats](../reading-writing/files.md).
