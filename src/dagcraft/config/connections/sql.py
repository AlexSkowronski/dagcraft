"""
The ``sql`` connection type.
"""

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SQLConfig(BaseModel):
    """
    A SQLAlchemy database URL, such as ``sqlite:///data/warehouse.db``.

    Write URLs that contain a password as ``${env:NAME}``. A relative SQLite
    path is relative to the pipeline file.
    """

    model_config = ConfigDict(extra="forbid")

    url: SecretStr = Field(min_length=1)
