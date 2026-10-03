"""
The ``sharepoint`` connection type.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SharePointConfig(BaseModel):
    """
    Files in ``folder`` of a SharePoint document ``library``.

    ``site`` is the site's address, e.g. ``contoso.sharepoint.com/sites/Finance``.
    """

    model_config = ConfigDict(extra="forbid")

    site: str = Field(min_length=1)
    library: str = Field(default="Documents", min_length=1)
    folder: str = ""

    @field_validator("site")
    @classmethod
    def normalise_site(cls, site: str) -> str:
        """
        Accept the address with or without ``https://`` and slashes.
        """
        site = re.sub(r"^https?://", "", site.strip()).strip("/")

        if "." not in site.partition("/")[0]:
            raise ValueError(
                "should be the site's address, such as "
                "'contoso.sharepoint.com/sites/Finance'."
            )
        return site
