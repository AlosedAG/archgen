"""Hubzy's questions and answers: seeded once per workspace, readable by
everyone, edited as one table by admins only, and kept per workspace."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from httpx import AsyncClient

from archscope_api.persistence.db import session_scope
from archscope_api.routers.deps import current_principal
from archscope_api.services import auth
from archscope_api.services.auth import Principal
from archscope_api.services.hubzy_seed import DEFAULT_TOPICS
from archscope_api.settings import Settings


async def test_defaults_are_seeded_once(client: AsyncClient) -> None:
    topics = (await client.get("/api/v1/hubzy/topics")).json()
    assert len(topics) == len(DEFAULT_TOPICS)
    assert any(t["question"] == "What is a SOW?" and t["page"] == "" for t in topics)
    assert any(t["question"] == "What does this page do?" and t["page"] == "discovery" for t in topics)

    # Emptying the table sticks: the defaults don't come back.
    assert (await client.put("/api/v1/hubzy/topics", json={"topics": []})).json() == []
    assert (await client.get("/api/v1/hubzy/topics")).json() == []


async def test_admin_edits_adds_reorders_and_removes_rows(client: AsyncClient) -> None:
    first, second, *_ = (await client.get("/api/v1/hubzy/topics")).json()
    saved = await client.put(
        "/api/v1/hubzy/topics",
        json={
            "topics": [
                {"page": "proposal", "question": "  How do I price a project?  ", "answer": "Use the pricing table."},
                {**second, "answer": "Edited answer."},
                {"id": first["id"], "page": first["page"], "question": first["question"], "answer": first["answer"]},
            ]
        },
    )
    assert saved.status_code == 200
    rows = saved.json()
    assert [r["question"] for r in rows] == ["How do I price a project?", second["question"], first["question"]]
    assert rows[1]["id"] == second["id"]
    assert rows[1]["answer"] == "Edited answer."
    assert rows[2]["id"] == first["id"]
    assert (await client.get("/api/v1/hubzy/topics")).json() == rows


async def test_blank_or_bad_rows_are_rejected(client: AsyncClient) -> None:
    for bad in (
        {"question": "   ", "answer": "x"},
        {"question": "Q", "answer": ""},
        {"question": "Q", "answer": "A", "page": "Not A Key"},
    ):
        assert (await client.put("/api/v1/hubzy/topics", json={"topics": [bad]})).status_code == 422


async def test_members_read_but_only_admins_edit_and_workspaces_are_separate(
    app: FastAPI, client: AsyncClient, settings: Settings, principal: Principal
) -> None:
    mine = await client.put("/api/v1/hubzy/topics", json={"topics": [{"question": "Ours?", "answer": "Yes."}]})
    assert mine.status_code == 200

    with session_scope(settings.database_url) as db:
        user = auth.create_user(db, email="ben@example.test", name="Ben", workspace_id=principal.workspace_id, role="member")
        ben = Principal(user.id, user.email, "Ben", principal.workspace_id, principal.workspace_name, "member")
    app.dependency_overrides[current_principal] = lambda: ben
    assert [t["question"] for t in (await client.get("/api/v1/hubzy/topics")).json()] == ["Ours?"]
    assert (await client.put("/api/v1/hubzy/topics", json={"topics": []})).status_code == 403

    with session_scope(settings.database_url) as db:
        other = auth.create_user(db, email="eve@elsewhere.test", workspace_name="Elsewhere", role="owner")
        outsider = Principal(other.id, other.email, "", other.memberships[0].workspace_id, "Elsewhere", "owner")
    app.dependency_overrides[current_principal] = lambda: outsider
    theirs = (await client.get("/api/v1/hubzy/topics")).json()
    assert len(theirs) == len(DEFAULT_TOPICS)  # their own fresh copy
    # Someone else's row id is treated as a new row, never edits the other workspace.
    ours_id = mine.json()[0]["id"]
    saved = (
        await client.put("/api/v1/hubzy/topics", json={"topics": [{"id": ours_id, "question": "Hijack", "answer": "No."}]})
    ).json()
    assert saved[0]["id"] != ours_id

    app.dependency_overrides[current_principal] = lambda: principal
    assert [t["question"] for t in (await client.get("/api/v1/hubzy/topics")).json()] == ["Ours?"]


async def test_two_first_requests_seed_only_once(client: AsyncClient) -> None:
    first, second = await asyncio.gather(client.get("/api/v1/hubzy/topics"), client.get("/api/v1/hubzy/topics"))
    assert first.status_code == second.status_code == 200
    topics = (await client.get("/api/v1/hubzy/topics")).json()
    assert len(topics) == len(DEFAULT_TOPICS)
