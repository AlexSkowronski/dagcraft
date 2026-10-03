"""
The ``sharepoint`` connection type: SharePoint document libraries.

Reached through Microsoft Graph. Requires the ``azure`` extra:
``pip install 'dagcraft-pipelines[azure]'``.
"""

import fnmatch
import io
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

from dagcraft.config.connections import SharePointConfig
from dagcraft.connections.files.base import FileConnection, FileMode
from dagcraft.connections.files.graph_client import (
    GRAPH_URL,
    HTTP_NOT_FOUND,
    GraphClient,
)
from dagcraft.exceptions import ExecutionError
from dagcraft.extras import require_extra
from dagcraft.paths import has_wildcards
from dagcraft.registry import register_connection


@register_connection("sharepoint")
class SharePointConnection(FileConnection):
    """
    Files in a SharePoint document library.

    Signs in with ``DefaultAzureCredential``, so the identity needs Graph
    permission to the site's files (for example ``Sites.Selected`` or
    ``Sites.ReadWrite.All`` for a service principal). Step paths are
    relative to ``folder`` in ``library``. Wildcards are allowed in file
    names, not in folder names. Uploads are limited to 250 MB.
    """

    config_model = SharePointConfig
    config: SharePointConfig

    def __init__(self, name: str, config: Any, base_dir: Path) -> None:
        require_extra("requests", "azure.identity", extra="azure")
        super().__init__(name, config, base_dir)
        self._graph: GraphClient | None = None
        self._drive_url = ""

    def open(self) -> None:
        self._graph = GraphClient(self.name)
        self._graph.open()
        self._drive_url = f"{GRAPH_URL}/drives/{self._find_drive_id()}"

    def close(self) -> None:
        if self._graph is not None:
            self._graph.close()
            self._graph = None

    @property
    def graph(self) -> GraphClient:
        """
        The open Graph client; raises if the connection isn't open.
        """
        if self._graph is None:
            raise self.not_open()
        return self._graph

    def check(self) -> str:
        # Opening already found the site and library; list the folder too.
        library = f"library '{self.config.library}' on {self.config.site}"
        folder = self.config.folder.strip("/")
        response = self.graph.request(
            "GET",
            self._item_url("", "children"),
            not_found_ok=True,
        )

        if not folder:
            return f"{library} is reachable"
        if response.status_code == HTTP_NOT_FOUND:
            return f"{library} is reachable; folder '{folder}' doesn't exist yet"
        return f"{library} is reachable; folder '{folder}' found"

    def check_pattern(self, pattern: str) -> None:
        folder = pattern.rpartition("/")[0]

        if has_wildcards(folder):
            raise ValueError(
                "SharePoint paths can only use wildcards in the file name, not "
                f"in folders ('{pattern}')."
            )

    @contextmanager
    def open_file(self, path: str, mode: FileMode) -> Generator[BinaryIO]:
        url = self._item_url(path, "content")

        if mode == "rb":
            yield io.BytesIO(self.graph.request("GET", url).content)
            return

        # Graph takes the whole file in one request, so collect it first.
        buffer = io.BytesIO()
        yield buffer
        self.graph.request(
            "PUT",
            url,
            data=buffer.getvalue(),
            headers={"Content-Type": "application/octet-stream"},
        )

    def glob(self, pattern: str) -> list[str]:
        folder, _, name_pattern = pattern.rpartition("/")
        url: str | None = self._item_url(folder, "children")
        matches: list[str] = []

        while url:
            page = self.graph.get_json(url)

            matches.extend(
                f"{folder}/{item['name']}" if folder else item["name"]
                for item in page.get("value", [])
                if "file" in item and fnmatch.fnmatchcase(item["name"], name_pattern)
            )

            url = page.get("@odata.nextLink")

        return matches

    def _find_drive_id(self) -> str:
        hostname, _, site_path = self.config.site.partition("/")
        site_url = f"{GRAPH_URL}/sites/{hostname}"

        if site_path:
            site_url += f":/{quote(site_path)}"

        site_id = self.graph.get_json(site_url)["id"]
        drives = self.graph.get_json(f"{GRAPH_URL}/sites/{site_id}/drives")

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
        """
        Graph URL for ``action`` on a file or folder, by path.
        """
        full_path = "/".join(
            part.strip("/") for part in (self.config.folder, path) if part.strip("/")
        )

        if not full_path:
            return f"{self._drive_url}/root/{action}"
        return f"{self._drive_url}/root:/{quote(full_path)}:/{action}"
