"""The workspace's standard SOW clauses: placeholder boilerplate the firm
owns and its admins edit once, then reuse in every proposal. Seeded from
archscope_domain.sow_clauses the first time it's needed."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from archscope_domain.sow_clauses import DEFAULT_CLAUSES

from ..persistence.models import SowClause, Workspace
from .auth import Principal
from .errors import Forbidden


@dataclass(frozen=True)
class ClauseInput:
    """One clause of the edited library; ``id`` is None for a new one."""

    id: str | None
    key: str
    title: str
    body: str
    include_by_default: bool


def _seed(db: Session, workspace_id: str) -> None:
    """Copy the standard clauses in, once per workspace (one conditional
    UPDATE claims the seeding, so two first requests can't both do it)."""
    claimed = db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id, Workspace.clauses_seeded.is_(False))
        .values(clauses_seeded=True)
        .execution_options(synchronize_session=False)
    )
    if getattr(claimed, "rowcount", 0) != 1:
        return
    for position, (key, title, body, on) in enumerate(DEFAULT_CLAUSES):
        db.add(SowClause(workspace_id=workspace_id, key=key, title=title, body=body, include_by_default=on, position=position))
    db.flush()


def list_clauses(db: Session, principal: Principal) -> list[SowClause]:
    _seed(db, principal.workspace_id)
    return list(
        db.scalars(select(SowClause).where(SowClause.workspace_id == principal.workspace_id).order_by(SowClause.position))
    )


def _slug(title: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:60] or "clause"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def save_clauses(db: Session, principal: Principal, rows: Sequence[ClauseInput]) -> list[SowClause]:
    """Replace the library with ``rows`` (admins only), in order. Known ids are
    updated, the rest added (with a key made from the title if none is given),
    missing ones deleted. Keys stay stable so SOW copies keep matching."""
    if not principal.is_admin:
        raise Forbidden("Only workspace owners and admins can edit the standard SOW clauses.")
    _seed(db, principal.workspace_id)
    existing = {c.id: c for c in db.scalars(select(SowClause).where(SowClause.workspace_id == principal.workspace_id))}
    kept: set[str] = set()
    keys: set[str] = set()
    for position, row in enumerate(rows):
        clause = existing.get(row.id) if row.id and row.id not in kept else None
        if clause is None:
            clause = SowClause(workspace_id=principal.workspace_id)
            db.add(clause)
            key = row.key if row.key and row.key not in keys else _slug(row.title, keys)
        else:
            kept.add(clause.id)
            key = clause.key if clause.key not in keys else _slug(row.title, keys)
        keys.add(key)
        if (clause.key, clause.title, clause.body, clause.include_by_default) != (
            key,
            row.title,
            row.body,
            row.include_by_default,
        ):
            clause.updated_by = principal.user_id
        clause.key, clause.title, clause.body = key, row.title, row.body
        clause.include_by_default, clause.position = row.include_by_default, position
    for clause_id, clause in existing.items():
        if clause_id not in kept:
            db.delete(clause)
    db.flush()
    return list_clauses(db, principal)


def as_sow_rows(clauses: list[SowClause]) -> list[dict[str, Any]]:
    """The library as SOW clause rows (domain form)."""
    return [{"Key": c.key, "Title": c.title, "Body": c.body, "Include": c.include_by_default} for c in clauses]
