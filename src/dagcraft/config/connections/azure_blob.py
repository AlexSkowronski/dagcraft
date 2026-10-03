"""The ``azure_blob`` connection type."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class AzureBlobConfig(BaseModel):
    """Files in ``container``, under ``prefix``.

    Set ``account`` to sign in as yourself (``az login``), a managed identity
    or a service principal, through ``DefaultAzureCredential``; or set
    ``connection_string``, usually as ``${env:NAME}``.
    """

    model_config = ConfigDict(extra="forbid")

    container: str = Field(min_length=1)
    prefix: str = ""
    account: str | None = Field(default=None, min_length=1)
    connection_string: SecretStr | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def check_sign_in(self) -> Self:
        """Exactly one way to sign in."""
        if (self.account is None) == (self.connection_string is None):
            raise ValueError(
                "Set exactly one of 'account' (sign in with "
                "DefaultAzureCredential) or 'connection_string'."
            )
        return self
