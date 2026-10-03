# SharePoint

Files in a SharePoint document library, through Microsoft Graph. Needs
`pip install "dagcraft-pipelines[azure]"`.

```yaml
connections:
  finance:
    type: sharepoint
    site: contoso.sharepoint.com/sites/Finance
    library: Documents           # optional; Documents by default
    folder: Reports/2026         # optional folder in the library

steps:
  - id: budget
    type: read
    connection: finance
    path: Budget 2026.xlsx       # Reports/2026/Budget 2026.xlsx
```

| Field | |
| --- | --- |
| `site` | The site's address, e.g. `contoso.sharepoint.com/sites/Finance` (with or without `https://`). |
| `library` | The document library. Defaults to `Documents`. |
| `folder` | Optional folder in the library; step paths are relative to it. |

## Signing in

dagcraft signs in with `DefaultAzureCredential`, like [Azure Blob
Storage](azure-blob.md#signing-in): a service principal's environment
variables, a managed identity, or your `az login`. The identity needs
Microsoft Graph permission to the site's files, such as `Sites.Selected`
(granted for this site) or `Sites.ReadWrite.All`.

## Good to know

- Wildcards work in file names (`daily/*.csv`), not in folder names; that's
  checked when the pipeline loads.
- Uploads are limited to 250 MB per file.
- Throttled and failed requests are retried, waiting as long as Graph asks.

## Checking

`--check-connections` finds the site and library, and says whether the
folder exists yet.

For the fields a read or write step takes, see [Files and
formats](../reading-writing/files.md).
