"""The workspace's stored credentials (HubSpot token, AI keys),
encrypted at rest. Plaintext only ever leaves this module to build an API
client for a request — it's never returned to the browser."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..persistence.models import WorkspaceSecret
from ..persistence.security import SecretBox
from .auth import Principal
from .errors import Forbidden, NotFound

HUBSPOT_TOKEN = "hubspot_token"
ANTHROPIC_KEY = "anthropic_api_key"
GEMINI_KEY = "gemini_api_key"
SECRET_NAMES = {
    HUBSPOT_TOKEN: "HubSpot private app token",
    GEMINI_KEY: "Gemini API key",
    ANTHROPIC_KEY: "Anthropic API key",
}


@dataclass(frozen=True)
class SecretStatus:
    name: str
    label: str
    configured: bool
    hint: str = ""
    updated_at: datetime | None = None


def list_status(db: Session, principal: Principal) -> list[SecretStatus]:
    stored = {
        s.name: s for s in db.scalars(select(WorkspaceSecret).where(WorkspaceSecret.workspace_id == principal.workspace_id))
    }
    return [
        SecretStatus(
            name,
            label,
            name in stored,
            stored[name].hint if name in stored else "",
            stored[name].updated_at if name in stored else None,
        )
        for name, label in SECRET_NAMES.items()
    ]


def set_secret(db: Session, box: SecretBox, principal: Principal, name: str, value: str) -> None:
    if not principal.is_admin:
        raise Forbidden("Only workspace owners and admins can change stored keys.")
    if name not in SECRET_NAMES:
        raise NotFound(f"Unknown credential '{name}'.")
    value = value.strip()
    secret = db.get(WorkspaceSecret, (principal.workspace_id, name))
    if secret is None:
        secret = WorkspaceSecret(workspace_id=principal.workspace_id, name=name)
        db.add(secret)
    secret.ciphertext = box.encrypt(value)
    secret.hint = value[-4:]
    secret.updated_at = datetime.now(UTC)
    secret.updated_by = principal.user_id
    db.flush()


def delete_secret(db: Session, principal: Principal, name: str) -> None:
    if not principal.is_admin:
        raise Forbidden("Only workspace owners and admins can change stored keys.")
    secret = db.get(WorkspaceSecret, (principal.workspace_id, name))
    if secret is not None:
        db.delete(secret)
        db.flush()


def reveal(db: Session, box: SecretBox, workspace_id: str, name: str) -> str | None:
    """The plaintext credential for server-side use, or None if not stored / undecryptable."""
    secret = db.get(WorkspaceSecret, (workspace_id, name))
    return box.decrypt(secret.ciphertext) if secret else None
