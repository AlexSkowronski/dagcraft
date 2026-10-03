"""
The ``local`` connection type.
"""

from pydantic import BaseModel, ConfigDict


class LocalConfig(BaseModel):
    """
    Files under ``root``; a relative root is relative to the folder you run from.
    """

    model_config = ConfigDict(extra="forbid")

    root: str = "."
