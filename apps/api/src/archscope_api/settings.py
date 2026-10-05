"""Runtime configuration, read from the environment (prefix ``ARCHSCOPE_``)
and an optional ``.env`` file. Secrets are ``SecretStr`` so they never
appear in logs, reprs, or error pages."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARCHSCOPE_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    # Browser origins allowed to call the API (the Next.js app).
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Discovery AI drafting. Unprefixed ANTHROPIC_API_KEY is accepted too, to
    # match the Anthropic SDK's own convention.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str | None = Field(default=None, validation_alias="ANTHROPIC_MODEL")

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings (cached). Tests override via dependency_overrides."""
    return Settings()
