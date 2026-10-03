"""
Readers: what a read step fetches. Importing registers the built-in ones.

A read step combines a connection (where), a reader for that kind of
connection (what), and, for files, a format (how the bytes become a table)::

    FileConnection  ->  FileReader  (path, wildcards)  ->  Format
    SQLConnection   ->  SQLReader   (query, query_file, table, partition)
"""

from dagcraft.readers.base import Reader
from dagcraft.readers.files import FileReader
from dagcraft.readers.sql import SQLReader

__all__ = ["FileReader", "Reader", "SQLReader"]
