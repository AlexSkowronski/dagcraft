"""
The engine: compiling a pipeline file and running it.

params.py              ${params.X} and ${env:X} references
compiler.py            config -> connections, prepared steps and a graph
graph.py               dependencies and run order
pipeline.py            Pipeline: from_yaml, plan, check_connections, run
executor.py            runs a compiled pipeline
scheduler.py           which step is ready next, and which to skip
step_runner.py         one step: inputs, retries, outcome
outputs.py             step outputs, dropped once no step needs them
connection_manager.py  connections opened on first use, closed after
workers.py             worker threads, or the calling thread
context.py             what a running step can reach
checks.py              proving a connection works
results.py             what a run, plan or check reports back
"""
