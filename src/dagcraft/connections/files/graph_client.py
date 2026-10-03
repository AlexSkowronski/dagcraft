"""
Signed-in requests to Microsoft Graph, which SharePoint is reached through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dagcraft.connections.azure_identity import create_credential
from dagcraft.exceptions import ExecutionError

if TYPE_CHECKING:
    import requests
    from azure.identity import DefaultAzureCredential

GRAPH_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
TIMEOUT_SECONDS = 120
HTTP_NOT_FOUND = 404
RETRY_STATUSES = (429, 500, 502, 503, 504)


class GraphClient:
    """
    Makes Graph requests with a fresh token, retrying throttling and blips.

    ``owner`` names the connection in error messages.
    """

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self._credential: DefaultAzureCredential | None = None
        self._session: requests.Session | None = None

    def open(self) -> None:
        """
        Sign in and start an HTTP session.
        """
        # Imported here so the azure extra is only needed when it's used.
        import requests  # noqa: PLC0415
        from requests.adapters import HTTPAdapter  # noqa: PLC0415
        from urllib3.util.retry import Retry  # noqa: PLC0415

        self._credential = create_credential()
        self._session = requests.Session()

        # Retry throttling and transient errors, waiting as Graph asks.
        retry = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=RETRY_STATUSES,
            allowed_methods=None,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    def close(self) -> None:
        """
        End the session and release the credential.
        """
        if self._session is not None:
            self._session.close()
            self._session = None

        if self._credential is not None:
            self._credential.close()
            self._credential = None

    def request(
        self,
        method: str,
        url: str,
        *,
        not_found_ok: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Send a request; raise ``ExecutionError`` with Graph's message if it fails.

        With ``not_found_ok``, a 404 response is returned instead of raised.
        """
        if self._session is None or self._credential is None:
            raise ExecutionError(f"Connection '{self.owner}' is not open.")

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
                f"Connection '{self.owner}': SharePoint returned "
                f"{response.status_code} for {method} {url}: {graph_message(response)}"
            )
        return response

    def get_json(self, url: str) -> Any:
        """
        GET ``url`` and return its JSON body.
        """
        return self.request("GET", url).json()


def graph_message(response: requests.Response) -> str:
    """
    The error message from a Graph error response, if it has one.
    """
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return response.text[:200] or response.reason
