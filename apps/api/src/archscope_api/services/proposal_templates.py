"""Shared proposal / SOW templates: a team member saves a filled-in
proposal (minus what identifies the client) under a name, and anyone in
the workspace can start a new proposal from it for a similar client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from archscope_domain import proposal as dp

from ..persistence.models import ProposalTemplate, User
from .auth import Principal
from .errors import Conflict, Forbidden, NotFound

Proposal = dict[str, Any]


@dataclass(frozen=True)
class TemplateSummary:
    template: ProposalTemplate
    created_by_name: str | None


def _get(db: Session, principal: Principal, template_id: str) -> ProposalTemplate:
    template = db.get(ProposalTemplate, template_id)
    if template is None or template.workspace_id != principal.workspace_id:
        raise NotFound("No such template in your workspace.")
    return template


def _summaries(db: Session, templates: list[ProposalTemplate]) -> list[TemplateSummary]:
    ids = {t.created_by for t in templates if t.created_by}
    names = {u.id: u.name or u.email for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    return [TemplateSummary(t, names.get(t.created_by or "")) for t in templates]


def list_templates(db: Session, principal: Principal) -> list[TemplateSummary]:
    """The workspace's templates, by name."""
    rows = list(
        db.scalars(
            select(ProposalTemplate)
            .where(ProposalTemplate.workspace_id == principal.workspace_id)
            .order_by(ProposalTemplate.name)
        )
    )
    return _summaries(db, rows)


def summary(db: Session, template: ProposalTemplate) -> TemplateSummary:
    return _summaries(db, [template])[0]


def save_template(
    db: Session, principal: Principal, *, name: str, description: str, proposal: Proposal, replace: bool = False
) -> ProposalTemplate:
    """Save ``proposal`` as a template (client details, dates and reference
    cleared). A template with the same name is replaced only if asked."""
    name = name.strip()
    data = dp.as_saved_template(proposal)
    existing = db.scalar(
        select(ProposalTemplate).where(ProposalTemplate.workspace_id == principal.workspace_id, ProposalTemplate.name == name)
    )
    if existing is not None:
        if not replace:
            raise Conflict(f"A template named '{name}' already exists. Replace it, or choose another name.")
        existing.data = data
        existing.description = description.strip()
        existing.updated_at = datetime.now(UTC)
        db.flush()
        return existing
    template = ProposalTemplate(
        workspace_id=principal.workspace_id, name=name, description=description.strip(), data=data, created_by=principal.user_id
    )
    db.add(template)
    db.flush()
    return template


def get_template(db: Session, principal: Principal, template_id: str) -> ProposalTemplate:
    return _get(db, principal, template_id)


def rename_template(
    db: Session, principal: Principal, template_id: str, *, name: str | None = None, description: str | None = None
) -> ProposalTemplate:
    template = _get(db, principal, template_id)
    if name is not None and name.strip() != template.name:
        clash = db.scalar(
            select(ProposalTemplate).where(
                ProposalTemplate.workspace_id == principal.workspace_id, ProposalTemplate.name == name.strip()
            )
        )
        if clash is not None:
            raise Conflict(f"A template named '{name.strip()}' already exists.")
        template.name = name.strip()
    if description is not None:
        template.description = description.strip()
    template.updated_at = datetime.now(UTC)
    db.flush()
    return template


def delete_template(db: Session, principal: Principal, template_id: str) -> None:
    """Templates are shared, so only their creator or a workspace admin may delete one."""
    template = _get(db, principal, template_id)
    if not (principal.is_admin or template.created_by == principal.user_id):
        raise Forbidden("Only the person who saved this template or a workspace admin can delete it.")
    db.delete(template)
    db.flush()


def apply_template(db: Session, principal: Principal, template_id: str, current: Proposal) -> Proposal:
    """``current`` restarted from the template, keeping its client details, dates and reference."""
    return dp.apply_saved_template(_get(db, principal, template_id).data, current)


def can_delete(principal: Principal, template: ProposalTemplate) -> bool:
    return principal.is_admin or template.created_by == principal.user_id
