# Files and formats

Read and write steps on file connections ([local](../connections/local.md),
[Azure Blob](../connections/azure-blob.md),
[SharePoint](../connections/sharepoint.md)) take:

| Field | |
| --- | --- |
| `path` | The file, relative to the connection. Reads can use [wildcards](#many-files-at-once). |
| `format` | The format, when the extension doesn't say: `csv`, `parquet`, `excel`, `json`, `jsonl` or `yaml`. |
| `args` | Options for the format's reader or writer (below). |
| `source_column` | For wildcard reads: names each row's (or document's) file. |

```yaml
  - id: orders
    type: read
    connection: lake
    path: orders/2026-10-02.csv
    args:
      sep: ";"

  - id: save
    type: write
    connection: lake
    path: clean/orders.parquet
    inputs:
      data: orders
```

## Two kinds of format

| Kind | Formats | Read as | Write |
| --- | --- | --- | --- |
| **Tables** | `csv`, `parquet`, `excel` | A pandas DataFrame | A DataFrame |
| **Documents** | `json`, `jsonl`, `yaml` | Plain Python data: dicts and lists | Dicts and lists as they are, or a DataFrame as one record per row |

| Format | Extensions | `args` go to |
| --- | --- | --- |
| `csv` | `.csv` | `pandas.read_csv` / `DataFrame.to_csv` |
| `parquet` | `.parquet`, `.pq` | `pandas.read_parquet` / `DataFrame.to_parquet` |
| `excel` | `.xlsx`, `.xlsm` | `pandas.read_excel` / `DataFrame.to_excel`; see [Excel](#excel) |
| `json` | `.json` | `json.load` / `json.dumps`, e.g. `indent: 2` |
| `jsonl` | `.jsonl`, `.ndjson` | `json.loads` / `json.dumps`, for each line |
| `yaml` | `.yaml`, `.yml` | Reading takes none; writing: `yaml.safe_dump` |

Table writes leave out the DataFrame index unless `args` sets `index: true`.
Excel needs `pip install "dagcraft-pipelines[excel]"`.

## Documents: JSON, JSON Lines and YAML

A JSON or YAML file is read as exactly what it holds, ready for your own
Python functions; a JSON Lines file as a list of its records:

```yaml
  - id: batch
    type: read
    connection: lake
    path: events/2026-10-02.json     # {"batch_id": "b1", "events": [...]}

  - id: summary
    type: python
    callable: my_functions:summarise  # def summarise(data): ... gets the dict
    inputs:
      data: batch

  - id: save
    type: write
    connection: lake
    path: summaries/2026-10-02.json   # whatever summarise returned
    inputs:
      data: summary
    args:
      indent: 2
```

Dates in what you write become ISO text (`2026-10-02`). YAML is read the
YAML 1.2 way: only `true` and `false` are booleans, so `on`, `yes` and `no`
stay text.

### Documents into a table

When you need a table, to write to SQL or CSV say, add a
[`flatten`](../steps.md#documents) step. Nested objects become dotted columns
(`user.id`), `record_path` takes the rows from a list inside each document,
and `meta` copies document fields onto each row:

```yaml
  - id: events
    type: transform
    inputs:
      data: batch
    operations:
      - flatten:
          record_path: events
          meta: [batch_id]
```

Writing documents where a table is needed (a CSV file, a SQL table) is an
error that says so.

## Many files at once

A read `path` with wildcards (`*`, `?`, `[...]`, and `**` for any depth of
folders) reads every matching file, in path order. No match is an error.

| Format | Many files give |
| --- | --- |
| `csv`, `parquet`, `excel` | One table. `source_column` adds a column naming each row's file. |
| `json`, `yaml` | A list of the documents. `source_column` adds a key naming the file to each object (or to each object in a list). |
| `jsonl` | One list of every file's records, each with the `source_column` key. |

```yaml
  - id: batches
    type: read
    connection: lake
    path: events/2026-10-*.json
    source_column: source_file       # each document gets source_file: events/...
```

## Excel

| Read `args` | Reads |
| --- | --- |
| (none) | The first sheet. |
| `sheet_name: Targets` | One sheet. |
| `sheet_name: [North, South]` | Those sheets, as one table with a `sheet` column naming each row's sheet. |
| `sheet_name: null` | Every sheet, as one table. |
| `sheet_column: region` | With several sheets: renames the `sheet` column. |

Sheets with different columns are best read by separate steps.

A write step with several inputs writes a workbook with one sheet per input,
named after the input:

```yaml
  - id: report
    type: write
    path: reports/regional.xlsx
    inputs:
      Summary: totals
      Monthly: monthly
```
