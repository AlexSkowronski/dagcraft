"""Signing in to Azure services that take an Entra ID token."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.identity import DefaultAzureCredential


def create_credential() -> DefaultAzureCredential:
    """A credential for whichever identity is available.

    ``DefaultAzureCredential`` tries, in turn, service principal environment
    variables, managed identity, then your ``az login``. Imported here so the
    ``azure`` extra is only needed when it's used.
    """
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    return DefaultAzureCredential()
