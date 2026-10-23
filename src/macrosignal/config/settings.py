"""Runtime settings: secrets and machine-specific overrides.

These values come only from environment variables or a local, git-ignored
``.env`` file. They are deliberately kept apart from the committed research
configs under ``configs/``, which must stay reproducible and secret-free.

Variables use the ``MACROSIGNAL_`` prefix. API keys additionally accept their
conventional unprefixed names (``FRED_API_KEY``, ``BEA_API_KEY``,
``MARKET_DATA_API_KEY``); the prefixed name wins when both are set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "MACROSIGNAL_"


def _key_field(name: str) -> Any:
    return Field(
        default=None,
        validation_alias=AliasChoices(f"{ENV_PREFIX}{name}", name),
    )


class Settings(BaseSettings):
    """Environment-derived settings; never loaded from research YAML."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    env: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")

    fred_api_key: SecretStr | None = _key_field("FRED_API_KEY")
    bea_api_key: SecretStr | None = _key_field("BEA_API_KEY")
    market_data_api_key: SecretStr | None = _key_field("MARKET_DATA_API_KEY")
