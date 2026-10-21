"""Hubzy's questions and answers: the in-app assistant offers these as
buttons (no AI involved). Every workspace starts with a copy of the defaults
and its admins edit the list as one table: add, change, reorder, remove."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..persistence.models import HubzyTopic, Workspace
from .auth import Principal
from .errors import Forbidden
from .hubzy_seed import DEFAULT_TOPICS


@dataclass(frozen=True)
class TopicInput:
    """One row of the edited table; ``id`` is None for a new row."""

    id: str | None
    page: str
    question: str
    answer: str


def _seed(db: Session, workspace_id: str) -> None:
    """Copy the default topics in, once per workspace. Flipping the flag is a
    single conditional UPDATE, so of two first requests racing (the panel
    and the editor, say) only one gets to insert."""
    claimed = db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id, Workspace.hubzy_seeded.is_(False))
        .values(hubzy_seeded=True)
        .execution_options(synchronize_session=False)
    )
    if getattr(claimed, "rowcount", 0) != 1:
        return
    for position, (page, question, answer) in enumerate(DEFAULT_TOPICS):
        db.add(HubzyTopic(workspace_id=workspace_id, page=page, question=question, answer=answer, position=position))
    db.flush()


def list_topics(db: Session, principal: Principal) -> list[HubzyTopic]:
    """The workspace's topics in table order."""
    _seed(db, principal.workspace_id)
    return list(
        db.scalars(
            select(HubzyTopic)
            .where(HubzyTopic.workspace_id == principal.workspace_id)
            .order_by(HubzyTopic.position, HubzyTopic.question)
        )
    )


def save_topics(db: Session, principal: Principal, rows: Sequence[TopicInput]) -> list[HubzyTopic]:
    """Replace the workspace's list with ``rows`` (admins only): rows with a
    known id are updated, the rest are added, and missing ones are deleted."""
    if not principal.is_admin:
        raise Forbidden("Only workspace owners and admins can edit Hubzy's answers.")
    _seed(db, principal.workspace_id)
    existing = {t.id: t for t in db.scalars(select(HubzyTopic).where(HubzyTopic.workspace_id == principal.workspace_id))}
    kept: set[str] = set()
    for position, row in enumerate(rows):
        topic = existing.get(row.id) if row.id and row.id not in kept else None
        if topic is None:
            topic = HubzyTopic(workspace_id=principal.workspace_id)
            db.add(topic)
        else:
            kept.add(topic.id)
        changed = (topic.page, topic.question, topic.answer) != (row.page, row.question, row.answer)
        topic.page, topic.question, topic.answer, topic.position = row.page, row.question, row.answer, position
        if changed:
            topic.updated_by = principal.user_id
    for topic_id, topic in existing.items():
        if topic_id not in kept:
            db.delete(topic)
    db.flush()
    return list_topics(db, principal)
