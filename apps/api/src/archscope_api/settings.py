"""Runtime configuration, read from the environment (prefix ``ARCHSCOPE_``)
and an optional ``.env`` file. Secrets are ``SecretStr`` so they never
appear in logs, reprs, or error pages."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
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
    # Gemini, for testing on Google's free tier: when a Gemini key is set
    # (here or on the Settings page) drafting uses Gemini instead of Claude.
    # Models are tried most accurate first — see archscope_domain.discovery
    # (override with GEMINI_MODELS, comma-separated).
    gemini_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))

    # Persistence. SQLite for local development and tests; PostgreSQL in
    # staging / production (postgresql+psycopg://user:pass@host/db).
    database_url: str = "sqlite:///./var/archscope.db"
    # Where saved documents' bytes live (a directory; swap for object storage later).
    blob_dir: str = "./var/blobs"
    # Encrypts stored credentials (HubSpot token, AI keys). Required
    # outside local/test; generate with `python -m archscope_api.cli secret-key`.
    secret_key: SecretStr | None = None

    # Sign-in sessions (HttpOnly cookie holding a random token; only its hash is stored).
    session_cookie: str = "archscope_session"
    session_days: int = 14
    # Optional Google sign-in (OIDC). Sign-ins are limited to existing users
    # and to these domains when creating users on first Google sign-in.
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_allowed_domains: list[str] = Field(default_factory=list)
    # Public URL of the web app (for OAuth redirects back after sign-in).
    web_url: str = "http://localhost:3000"

    # Self sign-up (email + password, confirmed with a code sent by email).
    signup_enabled: bool = True
    # Outgoing email (verification codes). The legacy app's FEEDBACK_SMTP_*
    # variables are accepted too. Without SMTP, local/test environments write
    # emails to `outbox_dir` (and log the code); elsewhere sign-up is off.
    smtp_host: str | None = Field(default=None, validation_alias=AliasChoices("ARCHSCOPE_SMTP_HOST", "FEEDBACK_SMTP_HOST"))
    smtp_port: int = Field(default=587, validation_alias=AliasChoices("ARCHSCOPE_SMTP_PORT", "FEEDBACK_SMTP_PORT"))
    smtp_username: str | None = Field(
        default=None, validation_alias=AliasChoices("ARCHSCOPE_SMTP_USERNAME", "FEEDBACK_SMTP_USERNAME")
    )
    smtp_password: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ARCHSCOPE_SMTP_PASSWORD", "FEEDBACK_SMTP_PASSWORD")
    )
    # "starttls" (587), "ssl" (465), or "none" (a local test relay only).
    smtp_security: str = "starttls"
    mail_from: str | None = Field(default=None, validation_alias=AliasChoices("ARCHSCOPE_MAIL_FROM", "FEEDBACK_FROM"))
    outbox_dir: str = "./var/outbox"

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"

    @property
    def is_dev(self) -> bool:
        return self.environment in ("local", "test")

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies everywhere except local http development."""
        return not self.is_dev

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_password and (self.mail_from or self.smtp_username))

    @property
    def email_delivery(self) -> str:
        """How emails go out: "smtp", "outbox" (local files, dev only), or "none"."""
        if self.smtp_enabled:
            return "smtp"
        return "outbox" if self.is_dev else "none"

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings (cached). Tests override via dependency_overrides."""
    return Settings()
