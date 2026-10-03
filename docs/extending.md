# Extending dagcraft

Everything a pipeline file can name (operations, step types, connection
types, formats) comes from a registry, and yours register the same way.
Register them before loading a pipeline that uses them, for example by
importing the module that defines them.

## Operations

For `transform` steps. Inputs and `args` arrive as keyword arguments:

```python
from dagcraft import register_operation


@register_operation("add_total")
def add_total(data, columns, name="total"):
    return data.assign(**{name: data[columns].sum(axis=1)})
```

```yaml
  - id: with_totals
    type: transform
    operation: add_total
    inputs: {data: sales}
    args: {columns: [q1, q2, q3, q4]}
```

## Step types

With their own fields, checked when the pipeline loads:

```python
from dagcraft import BaseStep, StepConfig, register_step


class SampleConfig(StepConfig):
    fraction: float


@register_step("sample")
class SampleStep(BaseStep):
    config_model = SampleConfig
    config: SampleConfig

    def describe(self):
        return f"sample {self.config.fraction:.0%}"

    def execute(self, context, inputs):
        (data,) = inputs.values()
        return data.sample(frac=self.config.fraction, random_state=0)
```

`execute` gets the step's inputs by name and an `ExecutionContext` with
`context.connection(name)` (opened on first use), `context.params` and
`context.logger`. `prepare(connections)` runs when the pipeline loads, to
check things early; raise `ValueError` there for a clear config error.

## Connections, readers and writers

A read or write step combines a **connection** (where the data is and how to
sign in), a **reader** or **writer** for that kind of connection (what to
read or write), and for files a **format**.

- **Other file storage:** subclass `FileConnection` and implement
  `open_file`, `glob` and `check`. The built-in file reader, writer and
  formats then work with it, wildcards included.
- **Anything else:** subclass `Connection`, and register a `Reader` (and a
  `Writer`) for it:

```python
from pydantic import BaseModel

from dagcraft import Connection, Reader, register_connection, register_reader


class ApiConfig(BaseModel):
    base_url: str


class ApiReadOptions(BaseModel):
    endpoint: str


@register_connection("api")
class ApiConnection(Connection):
    config_model = ApiConfig              # the connection's fields

    def open(self): ...                   # sign in, create a session
    def close(self): ...
    def check(self):                      # one cheap real request
        return "reachable"


@register_reader(ApiConnection)
class ApiReader(Reader):
    options_model = ApiReadOptions        # the read step's fields

    def describe(self):
        return self.options.endpoint

    def read(self, connection):
        ...  # fetch self.options.endpoint with the connection's session
```

## Formats

Subclass `Format`, list its `extensions`, implement `read` and `write`, and
use `register_format`. For a document format (read as plain data), subclass
`DocumentFormat` (from `dagcraft.formats`) instead; it lists several
files' documents together.
