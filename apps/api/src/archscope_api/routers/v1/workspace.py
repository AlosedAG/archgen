"""Workspace settings: its members, and the stored HubSpot token and AI
keys (values go in, only their status comes out)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ...schemas.workspace import Member, ModuleState, ModuleStateSave, SecretSet, SecretStatus
from ...services import projects, workspace_secrets, workspace_state
from ...services.errors import Conflict
from ..deps import DbDep, PrincipalDep, SecretBoxDep

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/members", response_model=list[Member], summary="Everyone in your workspace (for assigning projects)")
def list_members(principal: PrincipalDep, db: DbDep) -> list[Member]:
    return [Member(id=p.id, name=p.name, email=p.email, role=role) for p, role in projects.list_members(db, principal)]


@router.get("/secrets", response_model=list[SecretStatus], summary="Which credentials are stored (never their values)")
def list_secrets(principal: PrincipalDep, db: DbDep) -> list[SecretStatus]:
    return [SecretStatus.model_validate(s) for s in workspace_secrets.list_status(db, principal)]


@router.put("/secrets/{name}", response_model=list[SecretStatus], summary="Store or replace a credential (admins)")
def set_secret(name: str, body: SecretSet, principal: PrincipalDep, db: DbDep, box: SecretBoxDep) -> list[SecretStatus]:
    workspace_secrets.set_secret(db, box, principal, name, body.value)
    return [SecretStatus.model_validate(s) for s in workspace_secrets.list_status(db, principal)]


@router.delete("/secrets/{name}", status_code=204, summary="Remove a stored credential (admins)")
def delete_secret(name: str, principal: PrincipalDep, db: DbDep) -> Response:
    workspace_secrets.delete_secret(db, principal, name)
    return Response(status_code=204)


@router.get("/state/{module}", response_model=ModuleState, summary="A workspace tool's saved working state")
def get_state(module: str, principal: PrincipalDep, db: DbDep) -> ModuleState:
    state = workspace_state.get_state(db, principal, module)
    if state is None:
        return ModuleState(module=module)
    return ModuleState(module=module, data=state.data, version=state.version, updated_at=state.updated_at)


@router.put("/state/{module}", response_model=ModuleState, summary="Save a workspace tool's working state")
def save_state(module: str, body: ModuleStateSave, request: Request, principal: PrincipalDep, db: DbDep) -> ModuleState:
    if int(request.headers.get("content-length") or 0) > projects.MAX_STATE_BYTES:
        raise Conflict("That's too much data to save in one go.")
    state = workspace_state.save_state(db, principal, module, body.data, expected_version=body.version)
    return ModuleState(module=module, data=state.data, version=state.version, updated_at=state.updated_at)
