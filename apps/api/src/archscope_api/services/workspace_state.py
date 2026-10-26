"""Saved working state for the workspace-wide tools (trackers that aren't
tied to one project: leads, integrations, the knowledge base, ...). Saves
are versioned exactly like a project's module state: a save based on an
older version is refused instead of silently overwriting someone's work."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..persistence.models import WorkspaceState
from .auth import Principal
from .errors import NotFound, VersionConflict

# The workspace tools (their page slugs, as in the web app's /tools/<slug>).
MODULES = (
    "schedule",
    "review-feedback",
    "ai-guide",
    "data-management",
    "customer-success",
    "knowledge-base",
    "subscriptions",
    "marketing-dashboard",
    "leads",
    "studio",
    "social",
    "integrations",
    "webhooks",
    "logs",
)


def _check(module: str) -> None:
    if module not in MODULES:
        raise NotFound(f"Unknown workspace tool '{module}'.")


def get_state(db: Session, principal: Principal, module: str) -> WorkspaceState | None:
    _check(module)
    return db.get(WorkspaceState, (principal.workspace_id, module))


def save_state(db: Session, principal: Principal, module: str, data: dict[str, Any], *, expected_version: int) -> WorkspaceState:
    """Save ``module``'s state; ``expected_version`` is the version the client loaded (0 for a first save)."""
    _check(module)
    state = db.get(WorkspaceState, (principal.workspace_id, module))
    current = state.version if state else 0
    if expected_version != current:
        raise VersionConflict(
            f"Someone else saved this page (version {current}, you had {expected_version}). Reload to continue."
        )
    if state is None:
        state = WorkspaceState(
            workspace_id=principal.workspace_id, module=module, data=data, version=1, updated_by=principal.user_id
        )
        db.add(state)
    else:
        state.data = data
        state.version = current + 1
        state.updated_at = datetime.now(UTC)
        state.updated_by = principal.user_id
    db.flush()
    return state
