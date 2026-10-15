"""Client projects: list / create / edit / delete, each module's saved
working state (versioned), and the project library of saved documents."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from ...persistence.models import Project as ProjectRow
from ...schemas.workspace import Document, ModuleState, ModuleStateSave, Person, Project, ProjectCreate, ProjectUpdate
from ...services import projects
from ...services.auth import Principal
from ...services.errors import Conflict
from ..deps import BlobStoreDep, DbDep, PrincipalDep, offload

router = APIRouter(prefix="/projects", tags=["projects"])


def _person(p: projects.Person | None) -> Person | None:
    return Person(id=p.id, name=p.name, email=p.email) if p else None


def _project(s: projects.ProjectSummary, principal: Principal) -> Project:
    p = s.project
    return Project.model_validate(
        {
            **{k: getattr(p, k) for k in ("id", "name", "client_name", "folder", "archived", "created_at", "updated_at")},
            "document_count": s.document_count,
            "lead": _person(s.lead),
            "last_edited_by": _person(s.last_edited_by),
            "can_delete": principal.is_admin or principal.user_id in (p.created_by, p.lead_user_id),
        }
    )


def _one(db: DbDep, principal: Principal, project: ProjectRow) -> Project:
    count = len(projects.list_documents(db, principal, project.id))
    return _project(projects.summarize(db, project, count), principal)


@router.get("", response_model=list[Project], summary="Projects in your workspace, most recently active first")
def list_projects(principal: PrincipalDep, db: DbDep, include_archived: bool = False) -> list[Project]:
    return [_project(s, principal) for s in projects.list_projects(db, principal, include_archived=include_archived)]


@router.post("", response_model=Project, status_code=201, summary="Create a project")
def create_project(body: ProjectCreate, principal: PrincipalDep, db: DbDep) -> Project:
    project = projects.create_project(
        db, principal, name=body.name, client_name=body.client_name, folder=body.folder, lead_user_id=body.lead_user_id
    )
    return _one(db, principal, project)


@router.get("/{project_id}", response_model=Project, summary="One project")
def get_project(project_id: str, principal: PrincipalDep, db: DbDep) -> Project:
    return _one(db, principal, projects.get_project(db, principal, project_id))


@router.patch("/{project_id}", response_model=Project, summary="Edit a project: name, client, folder, person in charge, archive")
def update_project(project_id: str, body: ProjectUpdate, principal: PrincipalDep, db: DbDep) -> Project:
    project = projects.update_project(
        db,
        principal,
        project_id,
        name=body.name,
        client_name=body.client_name,
        folder=body.folder,
        lead_user_id=body.lead_user_id,
        clear_lead="lead_user_id" in body.model_fields_set and body.lead_user_id is None,
        archived=body.archived,
    )
    return _one(db, principal, project)


@router.delete("/{project_id}", status_code=204, summary="Delete a project with all its saved work and documents")
def delete_project(project_id: str, principal: PrincipalDep, db: DbDep, blobs: BlobStoreDep) -> Response:
    projects.delete_project(db, blobs, principal, project_id)
    return Response(status_code=204)


@router.get("/{project_id}/state/{module}", response_model=ModuleState, summary="A module's saved working state")
def get_state(project_id: str, module: str, principal: PrincipalDep, db: DbDep) -> ModuleState:
    state = projects.get_state(db, principal, project_id, module)
    if state is None:
        return ModuleState(module=module)
    return ModuleState(module=module, data=state.data, version=state.version, updated_at=state.updated_at)


@router.put("/{project_id}/state/{module}", response_model=ModuleState, summary="Save a module's working state")
def save_state(
    project_id: str, module: str, body: ModuleStateSave, request: Request, principal: PrincipalDep, db: DbDep
) -> ModuleState:
    if int(request.headers.get("content-length") or 0) > projects.MAX_STATE_BYTES:
        raise Conflict("That's too much data to save in one go.")
    state = projects.save_state(db, principal, project_id, module, body.data, expected_version=body.version)
    return ModuleState(module=module, data=state.data, version=state.version, updated_at=state.updated_at)


@router.get("/{project_id}/documents", response_model=list[Document], summary="The project library")
def list_documents(project_id: str, principal: PrincipalDep, db: DbDep) -> list[Document]:
    return [Document.model_validate(d) for d in projects.list_documents(db, principal, project_id)]


@router.post(
    "/{project_id}/documents",
    response_model=Document,
    status_code=201,
    summary="Save a file to the project library (raw file bytes as the request body)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def save_document(
    project_id: str,
    request: Request,
    principal: PrincipalDep,
    db: DbDep,
    blobs: BlobStoreDep,
    document_type: Annotated[str, Query(min_length=1, max_length=120)],
    filename: Annotated[str, Query(min_length=1, max_length=300)],
    title: Annotated[str, Query(max_length=300)] = "",
) -> Document:
    content = await request.body()
    if len(content) > projects.MAX_DOCUMENT_BYTES:
        raise Conflict("Files over 25 MB can't be saved to the library.")
    document = await offload(
        projects.save_document,
        db,
        blobs,
        principal,
        project_id,
        document_type=document_type,
        title=title or filename,
        filename=filename,
        media_type=request.headers.get("content-type", "application/octet-stream").split(";")[0],
        content=content,
    )
    return Document.model_validate(document)


@router.get("/{project_id}/documents/{document_id}", response_class=Response, summary="Download a saved document")
def download_document(project_id: str, document_id: str, principal: PrincipalDep, db: DbDep, blobs: BlobStoreDep) -> Response:
    document, content = projects.get_document(db, blobs, principal, project_id, document_id)
    return Response(
        content=content,
        media_type=document.media_type,
        headers={"Content-Disposition": f'attachment; filename="{document.filename}"'},
    )


@router.delete("/{project_id}/documents/{document_id}", status_code=204, summary="Delete a saved document")
def delete_document(project_id: str, document_id: str, principal: PrincipalDep, db: DbDep, blobs: BlobStoreDep) -> Response:
    projects.delete_document(db, blobs, principal, project_id, document_id)
    return Response(status_code=204)
