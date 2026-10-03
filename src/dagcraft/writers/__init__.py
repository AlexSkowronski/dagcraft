"""
Writers: where a write step puts its data. Importing registers the built-in ones.

FileConnection  ->  FileWriter  (path)  ->  Format
SQLConnection   ->  SQLWriter   (table, if_exists)
"""

from dagcraft.writers.base import Writer
from dagcraft.writers.files import FileWriter
from dagcraft.writers.sql import SQLWriter

__all__ = ["FileWriter", "SQLWriter", "Writer"]
