# Local files

A connection called `local`, rooted at the folder you run from, is always
there, so steps that read or write local files need no `connections`
entry. `connection` defaults to `local`:

```yaml
steps:
  - id: orders
    type: read
    path: data/orders.csv         # relative to the folder you run from
```

Define your own to give a folder a name, or to point somewhere else:

```yaml
connections:
  landing:
    type: local
    root: data/landing            # relative to the folder you run from
  archive:
    type: local
    root: D:/data/archive         # or an absolute path

steps:
  - id: orders
    type: read
    connection: landing
    path: orders.csv              # relative to the connection's root
```

| Field | |
| --- | --- |
| `root` | The folder step paths are relative to. Defaults to the folder you run from. |

## Writing

Folders are created as needed. A file is written under a temporary name and
only then moved into place, so a failed write leaves the old file as it
was.

## Checking

`--check-connections` reports whether the folder exists, or that it will be
created when written to.

For the fields a read or write step takes (`path`, `format`, wildcards, and
so on), see [Files and formats](../reading-writing/files.md).
