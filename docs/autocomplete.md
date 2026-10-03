# Autocomplete in VS Code

VS Code can suggest everything a pipeline file can say as you type, and
underline mistakes before you run anything:

- **Suggestions** for step types, connection types, operations and their
  options, with each one's description.
- **Red squiggles** under typos, missing fields and wrong values: `fliter`,
  `pth:`, `if_exists: upsrt`, `join: {lft: orders}`.
- **Descriptions on hover**, the same as in this guide.

It works through JSON Schemas: descriptions of pipeline files that dagcraft
builds from the same rules it checks files against.

## Set it up

1. Install the **YAML** extension by Red Hat (`redhat.vscode-yaml`).
2. Tell it which files are pipelines. In your project, create
   `.vscode/settings.json`:

    ```json
    {
      "yaml.schemas": {
        "https://alexskowronski.github.io/dagcraft/schemas/pipeline.json": "configs/*.yaml",
        "https://alexskowronski.github.io/dagcraft/schemas/connections.json": "connections.yaml"
      }
    }
    ```

    Change `configs/*.yaml` to wherever your pipelines live; it can be a
    list of patterns. `connections.yaml` is your [shared
    connections](pipeline-file.md#sharing-connections) file.

That's all: open a pipeline file and press ++ctrl+space++ anywhere to see
what can go there.

!!! tip "One file at a time"
    Instead of the setting, the first line of a file can say which schema
    it uses:

    ```yaml
    # yaml-language-server: $schema=https://alexskowronski.github.io/dagcraft/schemas/pipeline.json
    ```

## Schemas of your own

The published schemas describe dagcraft's built-in steps, connections and
operations, as of the latest code. To include [your own](extending.md), or
to match the version you have installed, write the schemas yourself after
importing what you register:

```bash
dagcraft --schema schemas
```

This writes `schemas/pipeline.json` and `schemas/connections.json`. Point
the setting at them instead:

```json
{
  "yaml.schemas": {
    "./schemas/pipeline.json": "configs/*.yaml",
    "./schemas/connections.json": "connections.yaml"
  }
}
```

Your own components are included when they're registered as the schemas
are written. From Python, after importing your modules:

```python
from pathlib import Path

import my_project.operations  # registers your operations
from dagcraft.schema import write_schemas

write_schemas(Path("schemas"))
```

Local files also suit networks that block GitHub.

## What it can't check

The editor only sees the file you're writing, so some checks still need
`dagcraft ... --dry-run`:

- **Which connection a step uses.** A `read` step is offered both file
  fields (`path`, `format`) and SQL fields (`query`, `table`); each says
  which connections take it. The dry run catches a `query` on a file
  connection.
- **Names across the file:** that `inputs` name real steps, that a `join`'s
  `right` is one of the step's inputs.
- **The machine:** environment variables, files, drivers and sign-in. For
  those, use `--check-connections`.

A value written as `${params.NAME}` or `${env:NAME}` is accepted wherever a
number, true/false or list is expected, since it's filled in when the
pipeline loads.
