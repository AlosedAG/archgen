"""Client projects, each module's saved working state, and the project
library of saved documents. Everything is scoped to the caller's workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..persistence.blobs import BlobStore
from ..persistence.models import Document, Project, ProjectState, new_id
from .auth import Principal
from .errors import Conflict, NotFound, VersionConflict

# Modules whose working state is stored per project (the web pages that use it).
MODULES = (
    "discovery",
    "stage_planner",
    "requirements",
    "evaluation_plan",
    "architecture",
    "diagram",
    "portal",  # the HubSpot snapshot + audit and property-audit results, shared by the Step 2 pages
    "proposal",
    "test_cases",
)
# Portal snapshots of large HubSpot accounts run to several MB.
MAX_STATE_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class ProjectSummary:
    project: Project
    document_count: int


def _get(db: Session, principal: Principal, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.workspace_id != principal.workspace_id:
        raise NotFound("No such project in your workspace.")
    return project


def list_projects(db: Session, principal: Principal, *, include_archived: bool = False) -> list[ProjectSummary]:
    counts = select(Document.project_id, func.count(Document.id).label("n")).group_by(Document.project_id).subquery()
    query = (
        select(Project, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.project_id == Project.id)
        .where(Project.workspace_id == principal.workspace_id)
        .order_by(Project.updated_at.desc())
    )
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    return [ProjectSummary(project, int(n)) for project, n in db.execute(query).all()]


def _ensure_unique_name(db: Session, principal: Principal, name: str, *, exclude_id: str | None = None) -> None:
    clash = db.scalar(select(Project).where(Project.workspace_id == principal.workspace_id, Project.name == name))
    if clash is not None and clash.id != exclude_id:
        raise Conflict(f"A project named '{name}' already exists.")


def create_project(db: Session, principal: Principal, *, name: str, client_name: str = "") -> Project:
    _ensure_unique_name(db, principal, name.strip())
    project = Project(
        workspace_id=principal.workspace_id,
        name=name.strip(),
        client_name=(client_name or name).strip(),
        created_by=principal.user_id,
    )
    db.add(project)
    db.flush()
    return project


def get_project(db: Session, principal: Principal, project_id: str) -> Project:
    return _get(db, principal, project_id)


def update_project(
    db: Session,
    principal: Principal,
    project_id: str,
    *,
    name: str | None = None,
    client_name: str | None = None,
    archived: bool | None = None,
) -> Project:
    project = _get(db, principal, project_id)
    if name is not None:
        _ensure_unique_name(db, principal, name.strip(), exclude_id=project.id)
        project.name = name.strip()
    if client_name is not None:
        project.client_name = client_name.strip()
    if archived is not None:
        project.archived = archived
    project.updated_at = datetime.now(UTC)
    db.flush()
    return project


# ---- Module state ------------------------------------------------------------


def get_state(db: Session, principal: Principal, project_id: str, module: str) -> ProjectState | None:
    _get(db, principal, project_id)
    if module not in MODULES:
        raise NotFound(f"Unknown module '{module}'.")
    return db.get(ProjectState, (project_id, module))


def save_state(
    db: Session, principal: Principal, project_id: str, module: str, data: dict[str, Any], *, expected_version: int
) -> ProjectState:
    """Save a module's state. ``expected_version`` is the version the client
    loaded (0 for a first save); a mismatch means someone else saved in
    between, and the save is refused rather than silently overwriting."""
    project = _get(db, principal, project_id)
    if module not in MODULES:
        raise NotFound(f"Unknown module '{module}'.")
    state = db.get(ProjectState, (project_id, module))
    current = state.version if state else 0
    if expected_version != current:
        raise VersionConflict(
            f"This {module.replace('_', ' ')} was saved elsewhere (version {current}, you had {expected_version}). Reload to continue."
        )
    now = datetime.now(UTC)
    if state is None:
        state = ProjectState(project_id=project_id, module=module, data=data, version=1, updated_by=principal.user_id)
        db.add(state)
    else:
        state.data = data
        state.version = current + 1
        state.updated_at = now
        state.updated_by = principal.user_id
    project.updated_at = now
    db.flush()
    return state


# ---- Documents (project library) -------------------------------------------------

_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def list_documents(db: Session, principal: Principal, project_id: str) -> list[Document]:
    _get(db, principal, project_id)
    return list(db.scalars(select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc())))


def save_document(
    db: Session,
    blobs: BlobStore,
    principal: Principal,
    project_id: str,
    *,
    document_type: str,
    title: str,
    filename: str,
    media_type: str,
    content: bytes,
) -> Document:
    project = _get(db, principal, project_id)
    if not content:
        raise Conflict("The document is empty.")
    doc_id = new_id()
    document = Document(
        id=doc_id,
        project_id=project_id,
        document_type=document_type.strip()[:120] or "Document",
        title=title.strip()[:300] or filename,
        filename=_SAFE.sub("_", filename).strip()[:300] or "document",
        media_type=media_type[:150] or "application/octet-stream",
        size_bytes=len(content),
        storage_key=f"{principal.workspace_id}/{project_id}/{doc_id}",
        created_by=principal.user_id,
    )
    blobs.put(document.storage_key, content)
    db.add(document)
    project.updated_at = datetime.now(UTC)
    db.flush()
    return document


def get_document(
    db: Session, blobs: BlobStore, principal: Principal, project_id: str, document_id: str
) -> tuple[Document, bytes]:
    _get(db, principal, project_id)
    document = db.get(Document, document_id)
    if document is None or document.project_id != project_id:
        raise NotFound("No such document in this project.")
    return document, blobs.get(document.storage_key)


def delete_document(db: Session, blobs: BlobStore, principal: Principal, project_id: str, document_id: str) -> None:
    _get(db, principal, project_id)
    document = db.get(Document, document_id)
    if document is None or document.project_id != project_id:
        raise NotFound("No such document in this project.")
    db.delete(document)
    db.flush()
    blobs.delete(document.storage_key)
