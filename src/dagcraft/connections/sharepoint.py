"""SharePoint document libraries, through Microsoft Graph.

Requires the ``azure`` extra (``pip install 'dagcraft-pipelines[azure]'``).
"""

from __future__ import annotations

import fnmatch
import io
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dagcraft.connections.files import FileConnection, has_wildcards
from dagcraft.exceptions import ExecutionError
from dagcraft.extras import require_extra
from dagcraft.registry import register_connection

if TYPE_CHECKING:
    import requests
    from azure.identity import DefaultAzureCredential

GRAPH_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
TIMEOUT_SECONDS = 120
HTTP_NOT_FOUND = 404


class SharePointConfig(BaseModel):
    """``site`` is the site's address, e.g. ``contoso.sharepoint.com/sites/Finance``."""

    model_config = ConfigDict(extra="forbid")

    site: str = Field(min_length=1)
    library: str = Field(default="Documents", min_length=1)
    folder: str = ""

    @field_validator("site")
    @classmethod
    def normalise_site(cls, site: str) -> str:
        site = re.sub(r"^https?://", "", site.strip()).strip("/")

        if "." not in site.partition("/")[0]:
            raise ValueError(
                "should be the site's address, such as "
                "'contoso.sharepoint.com/sites/Finance'."
            )
        return site


@register_connection("sharepoint")
class SharePointConnection(FileConnection):
    """Files in a SharePoint document library.

    Signs in with ``DefaultAzureCredential`` and talks to Microsoft Graph, so
    the identity needs Graph permission to the site's files (for example
    ``Sites.Selected`` or ``Sites.ReadWrite.All`` for a service principal).
    Step paths are relative to ``folder`` in ``library``. Wildcards are
    allowed in file names, not in folder names. Uploads are limited to
    250 MB.
    """

    config_model = SharePointConfig
    config: SharePointConfig

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        require_extra("requests", "azure.identity", extra="azure")
        super().__init__(name, config, base_dir)
        self._credential: DefaultAzureCredential | None = None
        self._session: requests.Session | None = None
        self._drive_url = ""

    def open(self) -> None:
        import requests  # noqa: PLC0415
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415
        from requests.adapters import HTTPAdapter  # noqa: PLC0415
        from urllib3.util.retry import Retry  # noqa: PLC0415

        self._credential = DefaultAzureCredential()
        self._session = requests.Session()

        # Retry throttling and transient errors, waiting as Graph asks.
        retry = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=None,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._drive_url = f"{GRAPH_URL}/drives/{self._find_drive_id()}"

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

        if self._credential is not None:
            self._credential.close()
            self._credential = None

    @contextmanager
    def open_file(self, path: str, mode: str) -> Iterator[BinaryIO]:
        if mode == "rb":
            response = self._request("GET", self._item_url(path, "content"))
            yield io.BytesIO(response.content)
        elif mode == "wb":
            buffer = io.BytesIO()
            yield buffer
            self._request(
                "PUT",
                self._item_url(path, "content"),
                data=buffer.getvalue(),
                headers={"Content-Type": "application/octet-stream"},
            )
        else:
            raise ValueError(f"Unsupported mode '{mode}'.")

    def glob(self, pattern: str) -> list[str]:
        folder, _, name_pattern = pattern.rpartition("/")

        if has_wildcards(folder):
            raise ExecutionError(
                f"Connection '{self.name}': SharePoint paths can only use "
                f"wildcards in the file name, not in folders ('{pattern}')."
            )

        url: str | None = self._item_url(folder, "children")
        matches: list[str] = []

        while url:
            page = self._request("GET", url).json()

            matches.extend(
                f"{folder}/{item['name']}" if folder else item["name"]
                for item in page.get("value", [])
                if "file" in item and fnmatch.fnmatchcase(item["name"], name_pattern)
            )

            url = page.get("@odata.nextLink")

        return matches

    def check(self) -> str:
        # Opening already found the site and library; list the folder too.
        library = f"library '{self.config.library}' on {self.config.site}"
        response = self._request(
            "GET",
            self._item_url("", "children"),
            not_found_ok=True,
        )

        if not self.config.folder.strip("/"):
            return f"{library} is reachable"

        folder = self.config.folder.strip("/")

        if response.status_code == HTTP_NOT_FOUND:
            return f"{library} is reachable; folder '{folder}' doesn't exist yet"
        return f"{library} is reachable; folder '{folder}' found"

    def _find_drive_id(self) -> str:
        hostname, _, site_path = self.config.site.partition("/")
        site_url = f"{GRAPH_URL}/sites/{hostname}"

        if site_path:
            site_url += f":/{quote(site_path)}"

        site_id = self._request("GET", site_url).json()["id"]
        drives = self._request("GET", f"{GRAPH_URL}/sites/{site_id}/drives").json()

        for drive in drives.get("value", []):
            if drive["name"] == self.config.library:
                return str(drive["id"])

        available = ", ".join(drive["name"] for drive in drives.get("value", []))
        raise ExecutionError(
            f"Connection '{self.name}': no document library named "
            f"'{self.config.library}' on {self.config.site}. "
            f"Available: {available or 'none'}."
        )

    def _item_url(self, path: str, action: str) -> str:
        """Graph URL for ``action`` on a file or folder, by path."""
        full_path = "/".join(
            part.strip("/") for part in (self.config.folder, path) if part.strip("/")
        )

        if not full_path:
            return f"{self._drive_url}/root/{action}"
        return f"{self._drive_url}/root:/{quote(full_path)}:/{action}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        not_found_ok: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        if self._session is None or self._credential is None:
            raise ExecutionError(f"Connection '{self.name}' is not open.")

        token = self._credential.get_token(GRAPH_SCOPE).token
        headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}

        response = self._session.request(
            method,
            url,
            headers=headers,
            timeout=TIMEOUT_SECONDS,
            **kwargs,
        )

        if response.status_code == HTTP_NOT_FOUND and not_found_ok:
            return response

        if not response.ok:
            raise ExecutionError(
                f"Connection '{self.name}': SharePoint returned "
                f"{response.status_code} for {method} {url}: {graph_message(response)}"
            )
        return response


def graph_message(response: requests.Response) -> str:
    """The error message from a Graph error response, if it has one."""
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return response.text[:200] or response.reason
