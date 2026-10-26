"""Workspace tools' saved state: versioned saves, known tools only, one
copy per workspace."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient

from archscope_api.persistence.db import session_scope
from archscope_api.routers.deps import current_principal
from archscope_api.services import auth
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings


async def test_save_load_and_version_conflicts(client: AsyncClient) -> None:
    empty = (await client.get("/api/v1/workspace/state/leads")).json()
    assert (empty["version"], empty["data"]) == (0, {})
    saved = await client.put("/api/v1/workspace/state/leads", json={"data": {"rows": [{"name": "Ana"}]}, "version": 0})
    assert saved.status_code == 200
    assert saved.json()["version"] == 1
    assert (await client.get("/api/v1/workspace/state/leads")).json()["data"] == {"rows": [{"name": "Ana"}]}
    stale = await client.put("/api/v1/workspace/state/leads", json={"data": {"rows": []}, "version": 0})
    assert stale.status_code == 409


async def test_unknown_tools_are_refused(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/workspace/state/nope")).status_code == 404
    assert (await client.put("/api/v1/workspace/state/nope", json={"data": {}, "version": 0})).status_code == 404


async def test_state_is_per_workspace(app: FastAPI, client: AsyncClient, settings: Settings) -> None:
    await client.put("/api/v1/workspace/state/logs", json={"data": {"rows": [1]}, "version": 0})
    with session_scope(settings.database_url) as db:
        other = auth.create_user(db, email="eve@elsewhere.test", workspace_name="Elsewhere", role="owner")
        outsider = Principal(other.id, other.email, "", other.memberships[0].workspace_id, "Elsewhere", "owner")
    app.dependency_overrides[current_principal] = lambda: outsider
    assert (await client.get("/api/v1/workspace/state/logs")).json()["version"] == 0
