"""Hubzy, the in-app assistant: his questions and answers (admins edit them)."""

from __future__ import annotations

from fastapi import APIRouter

from ...persistence.models import HubzyTopic as HubzyTopicRow
from ...schemas.hubzy import HubzyTopic, HubzyTopicsSave
from ...services import hubzy
from ..deps import DbDep, PrincipalDep

router = APIRouter(prefix="/hubzy", tags=["hubzy"])


def _out(rows: list[HubzyTopicRow]) -> list[HubzyTopic]:
    return [HubzyTopic.model_validate(r) for r in rows]


@router.get("/topics", response_model=list[HubzyTopic], summary="The questions Hubzy answers, in order")
def list_topics(principal: PrincipalDep, db: DbDep) -> list[HubzyTopic]:
    return _out(hubzy.list_topics(db, principal))


@router.put("/topics", response_model=list[HubzyTopic], summary="Replace the whole list of questions and answers (admins)")
def save_topics(body: HubzyTopicsSave, principal: PrincipalDep, db: DbDep) -> list[HubzyTopic]:
    rows = [hubzy.TopicInput(t.id, t.page, t.question, t.answer) for t in body.topics]
    return _out(hubzy.save_topics(db, principal, rows))
