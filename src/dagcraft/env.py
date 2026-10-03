"""Loading environment variables from a ``.env`` file."""

from pathlib import Path

from dotenv import load_dotenv

from dagcraft.exceptions import ConfigError


def load_env_file(path: Path) -> None:
    """Add the variables in ``path`` to the environment.

    Variables already set in the environment keep their values, so a real
    environment (a scheduler, a CI secret) wins over the file. Loading into
    the environment, rather than a private dict, lets libraries that read it
    themselves, such as ``DefaultAzureCredential``, see the values too.
    """
    if not path.is_file():
        raise ConfigError(f"env_file not found: {path}")

    load_dotenv(path, override=False)
