"""Projects: folders, person in charge, last edited by, editing and
deleting (with permissions), the members list; and the Feedback button's
endpoint, which emails reports with screenshots to the app owner."""

from __future__ import annotations

import base64

from fastapi import FastAPI
from httpx import AsyncClient

from archscope_api.mail import OutboxMailer
from archscope_api.persistence.db import session_scope
from archscope_api.routers.deps import current_principal, get_mailer
from archscope_api.services import auth
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


def _member(settings: Settings, principal: Principal, email: str = "ben@example.test") -> Principal:
    """A plain member of the principal's workspace."""
    with session_scope(settings.database_url) as db:
        user = auth.create_user(db, email=email, name="Ben", workspace_id=principal.workspace_id, role="member")
        return Principal(user.id, user.email, "Ben", principal.workspace_id, principal.workspace_name, "member")


async def test_new_project_has_folder_creator_in_charge_and_last_editor(client: AsyncClient, principal: Principal) -> None:
    created = await client.post("/api/v1/projects", json={"name": "Acme CRM", "folder": "Acme"})
    assert created.status_code == 201
    project = created.json()
    assert project["folder"] == "Acme"
    assert project["lead"]["id"] == principal.user_id
    assert project["last_edited_by"]["id"] == principal.user_id
    assert project["can_delete"] is True


async def test_members_list_and_assigning_the_person_in_charge(
    app: FastAPI, client: AsyncClient, settings: Settings, principal: Principal
) -> None:
    ben = _member(settings, principal)
    members = (await client.get("/api/v1/workspace/members")).json()
    assert {m["email"] for m in members} == {principal.email, "ben@example.test"}

    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    edited = await client.patch(
        f"/api/v1/projects/{pid}", json={"lead_user_id": ben.user_id, "folder": "Clients/Acme", "client_name": "Acme Inc"}
    )
    assert edited.status_code == 200
    assert edited.json()["lead"]["name"] == "Ben"
    assert edited.json()["folder"] == "Clients/Acme"
    assert edited.json()["client_name"] == "Acme Inc"

    cleared = await client.patch(f"/api/v1/projects/{pid}", json={"lead_user_id": None})
    assert cleared.json()["lead"] is None
    outsider = await client.patch(f"/api/v1/projects/{pid}", json={"lead_user_id": "not-a-member"})
    assert outsider.status_code == 404


async def test_saving_work_records_who_last_edited(
    app: FastAPI, client: AsyncClient, settings: Settings, principal: Principal
) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    ben = _member(settings, principal)
    app.dependency_overrides[current_principal] = lambda: ben
    saved = await client.put(f"/api/v1/projects/{pid}/state/discovery", json={"data": {"x": 1}, "version": 0})
    assert saved.status_code == 200
    project = (await client.get(f"/api/v1/projects/{pid}")).json()
    assert project["last_edited_by"]["name"] == "Ben"
    listed = (await client.get("/api/v1/projects")).json()[0]
    assert listed["last_edited_by"]["name"] == "Ben"


async def test_delete_is_for_the_person_in_charge_creator_or_admins(
    app: FastAPI, client: AsyncClient, settings: Settings, principal: Principal
) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    await client.put(f"/api/v1/projects/{pid}/state/discovery", json={"data": {"x": 1}, "version": 0})
    upload = await client.post(
        f"/api/v1/projects/{pid}/documents",
        params={"document_type": "Notes", "filename": "a.txt"},
        content=b"hello",
        headers={"Content-Type": "text/plain"},
    )
    assert upload.status_code == 201

    ben = _member(settings, principal)
    app.dependency_overrides[current_principal] = lambda: ben
    assert (await client.get(f"/api/v1/projects/{pid}")).json()["can_delete"] is False
    assert (await client.delete(f"/api/v1/projects/{pid}")).status_code == 403

    app.dependency_overrides[current_principal] = lambda: principal
    assert (await client.delete(f"/api/v1/projects/{pid}")).status_code == 204
    assert (await client.get(f"/api/v1/projects/{pid}")).status_code == 404
    assert (await client.get("/api/v1/projects")).json() == []


# ---- Feedback ------------------------------------------------------------------------------


async def test_feedback_is_emailed_to_the_owner_with_screenshots(
    app: FastAPI, client: AsyncClient, principal: Principal, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    outbox = OutboxMailer(tmp_path / "outbox")
    app.dependency_overrides[get_mailer] = lambda: outbox
    response = await client.post(
        "/api/v1/feedback",
        json={
            "kind": "idea",
            "message": "Auto-number requirement rows\nR-1, R-2…",
            "page": "Proposal & SOW Builder",
            "path": "/projects/x/proposal",
            "project_name": "Acme",
            "attachments": [{"filename": "shot.png", "content_type": "image/png", "data": PNG}],
        },
    )
    assert response.status_code == 202
    (sent,) = outbox.sent
    assert sent.to == "aylin@sonamation.com"
    assert sent.reply_to == principal.email
    assert sent.subject.startswith("[ArchitectureScope Idea] Proposal & SOW Builder")
    assert "Project: Acme" in sent.text
    assert principal.email in sent.text
    assert sent.attachments[0].filename == "shot.png"
    assert sent.attachments[0].data.startswith(b"\x89PNG")


async def test_feedback_validation_and_no_email_configured(app: FastAPI, client: AsyncClient, tmp_path) -> None:  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_mailer] = lambda: OutboxMailer(tmp_path / "outbox")
    empty = await client.post("/api/v1/feedback", json={"kind": "bug", "message": "  "})
    assert empty.status_code == 422
    not_image = await client.post(
        "/api/v1/feedback",
        json={
            "kind": "bug",
            "message": "x",
            "attachments": [{"filename": "a.exe", "content_type": "application/x-msdownload", "data": PNG}],
        },
    )
    assert not_image.status_code == 422
    garbage = await client.post(
        "/api/v1/feedback",
        json={"kind": "bug", "message": "x", "attachments": [{"filename": "a.png", "content_type": "image/png", "data": "%%%"}]},
    )
    assert garbage.status_code == 422

    app.dependency_overrides[get_mailer] = lambda: None
    off = await client.post("/api/v1/feedback", json={"kind": "bug", "message": "It broke"})
    assert off.status_code == 503
    assert "aylin@sonamation.com" in off.json()["detail"]
