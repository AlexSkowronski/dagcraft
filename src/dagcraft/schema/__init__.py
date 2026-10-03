"""
JSON Schemas for pipeline files, so editors can autocomplete and check them.

    pipeline.json     pipeline files
    connections.json  files of shared connections, which pipelines include

Built from what's registered (connection and step types, readers and
writers, operations), so your own components are in them too. Write them
with ``dagcraft --schema DIR``; the guide publishes the built-in ones.
"""

from dagcraft.schema.build import connections_schema, pipeline_schema, write_schemas

__all__ = ["connections_schema", "pipeline_schema", "write_schemas"]
