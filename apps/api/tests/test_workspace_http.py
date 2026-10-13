"""Accounts, projects, saved module state, the project library, stored
credentials, and the migrations that create their tables."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.cli import alembic_config
from archscope_api.main import create_app
from archscope_api.persistence.db import get_engine, session_scope
from archscope_api.persistence.models import Base
from archscope_api.persistence.security import SecretBox
from archscope_api.routers.deps import current_principal, get_settings
from archscope_api.services import auth, workspace_secrets
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings

# ---- Sign-in ------------------------------------------------------------------


async def test_api_requires_sign_in(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/api/v1/projects")
    assert response.status_code == 401
    assert response.json()["type"].endswith("/not-signed-in")
    assert (await anon_client.get("/healthz")).status_code == 200
    config = (await anon_client.get("/api/v1/auth/config")).json()
    assert (config["password"], config["google"]) == (True, False)


async def test_sign_in_sets_an_httponly_cookie_and_sign_out_ends_the_session(
    anon_client: AsyncClient, principal: Principal, test_password: str
) -> None:
    bad = await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": "nope"})
    assert bad.status_code == 401
    assert bad.json()["type"].endswith("/sign-in-failed")

    response = await anon_client.post(
        "/api/v1/auth/sign-in", json={"email": f" {principal.email.upper()} ", "password": test_password}
    )
    assert response.status_code == 200
    assert response.json()["workspace_name"] == "SonaMation"
    assert response.json()["is_admin"] is True
    cookie = response.headers["set-cookie"]
    assert "archscope_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie

    assert (await anon_client.get("/api/v1/auth/me")).json()["email"] == principal.email
    assert (await anon_client.get("/api/v1/projects")).status_code == 200

    assert (await anon_client.post("/api/v1/auth/sign-out")).status_code == 204
    anon_client.cookies.clear()
    assert (await anon_client.get("/api/v1/auth/me")).status_code == 401


async def test_a_signed_out_token_is_dead_even_if_replayed(
    anon_client: AsyncClient, principal: Principal, test_password: str
) -> None:
    await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    token = anon_client.cookies.get("archscope_session")
    await anon_client.post("/api/v1/auth/sign-out")
    anon_client.cookies.set("archscope_session", token or "")
    assert (await anon_client.get("/api/v1/auth/me")).status_code == 401


def _blob_files(root: str, name: str) -> list[Path]:
    return list(Path(root).rglob(name))


# ---- Projects, state, documents ------------------------------------------------------


async def test_projects_crud(client: AsyncClient) -> None:
    created = await client.post("/api/v1/projects", json={"name": "Bright Smiles"})
    assert created.status_code == 201
    project = created.json()
    assert project["client_name"] == "Bright Smiles"
    assert (await client.post("/api/v1/projects", json={"name": "Bright Smiles"})).status_code == 409
    renamed = await client.patch(f"/api/v1/projects/{project['id']}", json={"client_name": "Bright Smiles Dental"})
    assert renamed.json()["client_name"] == "Bright Smiles Dental"
    await client.patch(f"/api/v1/projects/{project['id']}", json={"archived": True})
    assert (await client.get("/api/v1/projects")).json() == []
    assert len((await client.get("/api/v1/projects?include_archived=true")).json()) == 1


async def test_module_state_is_versioned(client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    empty = (await client.get(f"/api/v1/projects/{pid}/state/discovery")).json()
    assert (empty["version"], empty["data"]) == (0, {})
    first = await client.put(f"/api/v1/projects/{pid}/state/discovery", json={"data": {"clientName": "Acme"}, "version": 0})
    assert first.json()["version"] == 1
    second = await client.put(f"/api/v1/projects/{pid}/state/discovery", json={"data": {"clientName": "Acme 2"}, "version": 1})
    assert second.json()["version"] == 2
    stale = await client.put(f"/api/v1/projects/{pid}/state/discovery", json={"data": {"clientName": "lost"}, "version": 1})
    assert stale.status_code == 409
    assert stale.json()["type"].endswith("/version-conflict")
    saved = (await client.get(f"/api/v1/projects/{pid}/state/discovery")).json()
    assert saved["data"] == {"clientName": "Acme 2"}
    # Timestamps carry their UTC offset (SQLite stores none), so browsers don't read them as local time.
    assert saved["updated_at"].endswith(("Z", "+00:00"))
    assert (await client.get(f"/api/v1/projects/{pid}/state/nope")).status_code == 404


async def test_project_library_round_trip(client: AsyncClient, settings: Settings) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    saved = await client.post(
        f"/api/v1/projects/{pid}/documents",
        params={"document_type": "Discovery Checklist", "filename": "Acme checklist.pdf"},
        content=b"%PDF-1.7 test",
        headers={"Content-Type": "application/pdf"},
    )
    assert saved.status_code == 201
    doc = saved.json()
    assert (doc["media_type"], doc["size_bytes"], doc["title"]) == ("application/pdf", 13, "Acme checklist.pdf")
    listing = (await client.get(f"/api/v1/projects/{pid}/documents")).json()
    assert [d["id"] for d in listing] == [doc["id"]]
    assert (await client.get(f"/api/v1/projects/{pid}")).json()["document_count"] == 1
    download = await client.get(f"/api/v1/projects/{pid}/documents/{doc['id']}")
    assert download.content == b"%PDF-1.7 test"
    assert 'filename="Acme checklist.pdf"' in download.headers["content-disposition"]
    assert (await client.delete(f"/api/v1/projects/{pid}/documents/{doc['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/projects/{pid}/documents")).json() == []
    assert not _blob_files(settings.blob_dir, doc["id"])


async def test_workspaces_are_isolated(app: FastAPI, settings: Settings, client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    with session_scope(settings.database_url) as db:
        other = auth.create_user(db, email="eve@elsewhere.test", workspace_name="Elsewhere", role="owner")
        outsider = Principal(other.id, other.email, "", other.memberships[0].workspace_id, "Elsewhere", "owner")
    app.dependency_overrides[current_principal] = lambda: outsider
    assert (await client.get("/api/v1/projects")).json() == []
    assert (await client.get(f"/api/v1/projects/{pid}")).status_code == 404
    assert (await client.get(f"/api/v1/projects/{pid}/state/discovery")).status_code == 404


# ---- Stored credentials --------------------------------------------------------------


async def test_secrets_are_stored_encrypted_and_never_returned(
    client: AsyncClient, settings: Settings, principal: Principal
) -> None:
    put = await client.put("/api/v1/workspace/secrets/anthropic_api_key", json={"value": "sk-ant-secret-1234"})
    assert put.status_code == 200
    status = {s["name"]: s for s in put.json()}
    assert status["anthropic_api_key"]["configured"] is True
    assert status["anthropic_api_key"]["hint"] == "1234"
    assert status["hubspot_token"]["configured"] is False
    assert "sk-ant-secret" not in put.text
    with session_scope(settings.database_url) as db:
        assert workspace_secrets.reveal(db, SecretBox(None), principal.workspace_id, "anthropic_api_key") == "sk-ant-secret-1234"
    assert (await client.delete("/api/v1/workspace/secrets/anthropic_api_key")).status_code == 204
    assert not {s["name"]: s for s in (await client.get("/api/v1/workspace/secrets")).json()}["anthropic_api_key"]["configured"]


async def test_only_admins_change_secrets(app: FastAPI, client: AsyncClient, principal: Principal) -> None:
    member = Principal(
        principal.user_id, principal.email, principal.name, principal.workspace_id, principal.workspace_name, "member"
    )
    app.dependency_overrides[current_principal] = lambda: member
    response = await client.put("/api/v1/workspace/secrets/hubspot_token", json={"value": "pat-na1-xxxxxxxx"})
    assert response.status_code == 403


async def test_stored_hubspot_token_is_used_when_no_header(settings: Settings, principal: Principal) -> None:
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[current_principal] = lambda: principal
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as http:
        missing = await http.post("/api/v1/portal/snapshot")
        assert missing.status_code == 400
        assert "Settings" in missing.json()["detail"]


# ---- Migrations ------------------------------------------------------------------------


def test_migrations_create_exactly_the_models_schema(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    command.upgrade(alembic_config(url), "head")
    with get_engine(url).connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], diff
