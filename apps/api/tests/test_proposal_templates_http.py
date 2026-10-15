"""Shared proposal templates: save a filled-in proposal (client details
cleared), list them for the workspace, start a new proposal from one
(keeping the new client's details), rename, replace and delete."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from archscope_api.persistence.db import session_scope
from archscope_api.routers.deps import current_principal
from archscope_api.services import auth
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings


async def _filled(client: AsyncClient) -> dict[str, Any]:
    proposal = (await client.get("/api/v1/proposals/default")).json()
    proposal["client"]["company"] = "Acme"
    proposal["client"]["email"] = "jane@acme.test"
    proposal["reference_number"] = "SOW-7"
    proposal["requirements"] = [{"id": "R-1", "requirement": "Sync contacts", "priority": "Must Have", "source": ""}]
    proposal["scope"] = [{"id": "S-1", "item": "Contact sync", "status": "In Scope", "requirement_ids": "R-1"}]
    return proposal


async def test_save_list_and_apply_a_template(client: AsyncClient) -> None:
    saved = await client.post(
        "/api/v1/proposals/templates",
        json={"name": "Dental clinic", "description": "Multi-location practices", "proposal": await _filled(client)},
    )
    assert saved.status_code == 201
    summary = saved.json()
    assert (summary["requirement_count"], summary["scope_count"], summary["can_delete"]) == (1, 1, True)

    listed = (await client.get("/api/v1/proposals/templates")).json()
    assert [t["name"] for t in listed] == ["Dental clinic"]

    new = (await client.get("/api/v1/proposals/default")).json()
    new["client"]["company"] = "Bright Smiles"
    started = await client.post(f"/api/v1/proposals/templates/{summary['id']}/apply", json={"proposal": new})
    assert started.status_code == 200
    doc = started.json()
    assert doc["client"]["company"] == "Bright Smiles"  # this deal's client kept
    assert doc["client"]["email"] == ""  # the template's client never leaks in
    assert doc["reference_number"] == ""
    assert doc["requirements"][0]["requirement"] == "Sync contacts"
    assert doc["scope"][0]["item"] == "Contact sync"


async def test_same_name_needs_replace_and_rename_works(client: AsyncClient) -> None:
    body = {"name": "Dental clinic", "proposal": await _filled(client)}
    first = (await client.post("/api/v1/proposals/templates", json=body)).json()
    clash = await client.post("/api/v1/proposals/templates", json=body)
    assert clash.status_code == 409
    replaced = await client.post("/api/v1/proposals/templates", json={**body, "replace": True})
    assert replaced.status_code == 201
    assert replaced.json()["id"] == first["id"]
    renamed = await client.patch(f"/api/v1/proposals/templates/{first['id']}", json={"name": "Dental (multi-site)"})
    assert renamed.json()["name"] == "Dental (multi-site)"


async def test_templates_are_shared_but_only_creator_or_admin_deletes(
    app: FastAPI, client: AsyncClient, settings: Settings, principal: Principal
) -> None:
    tid = (await client.post("/api/v1/proposals/templates", json={"name": "Gym", "proposal": await _filled(client)})).json()["id"]
    with session_scope(settings.database_url) as db:
        user = auth.create_user(db, email="ben@example.test", name="Ben", workspace_id=principal.workspace_id, role="member")
        ben = Principal(user.id, user.email, "Ben", principal.workspace_id, principal.workspace_name, "member")
    app.dependency_overrides[current_principal] = lambda: ben
    listed = (await client.get("/api/v1/proposals/templates")).json()
    assert [t["name"] for t in listed] == ["Gym"]
    assert listed[0]["can_delete"] is False
    assert (await client.delete(f"/api/v1/proposals/templates/{tid}")).status_code == 403

    with session_scope(settings.database_url) as db:
        other = auth.create_user(db, email="eve@elsewhere.test", workspace_name="Elsewhere", role="owner")
        outsider = Principal(other.id, other.email, "", other.memberships[0].workspace_id, "Elsewhere", "owner")
    app.dependency_overrides[current_principal] = lambda: outsider
    assert (await client.get("/api/v1/proposals/templates")).json() == []
    assert (await client.delete(f"/api/v1/proposals/templates/{tid}")).status_code == 404

    app.dependency_overrides[current_principal] = lambda: principal
    assert (await client.delete(f"/api/v1/proposals/templates/{tid}")).status_code == 204
    assert (await client.get("/api/v1/proposals/templates")).json() == []
