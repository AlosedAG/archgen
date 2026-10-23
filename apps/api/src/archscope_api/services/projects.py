"""Client projects, each module's saved working state, and the project
library of saved documents. Everything is scoped to the caller's workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..persistence.blobs import BlobStore
from ..persistence.models import Document, Membership, Project, ProjectState, User, new_id
from .auth import Principal
from .errors import Conflict, Forbidden, NotFound, VersionConflict

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
    "tasks",  # the internal task tracker (Tasks & progress)
    "schedule",  # the Schedule Planner: meeting plan settings and meetings
)
# Portal snapshots of large HubSpot accounts run to several MB.
MAX_STATE_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class Person:
    """A workspace member as shown on a project (in charge / last edited by)."""

    id: str
    name: str
    email: str


@dataclass(frozen=True)
class ProjectSummary:
    project: Project
    document_count: int
    lead: Person | None = None
    last_edited_by: Person | None = None


def _people(db: Session, ids: set[str | None]) -> dict[str, Person]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    return {u.id: Person(u.id, u.name or u.email, u.email) for u in db.scalars(select(User).where(User.id.in_(wanted)))}


def people(db: Session, ids: set[str | None]) -> dict[str, Person]:
    """Workspace users by id, as shown on projects."""
    return _people(db, ids)


def roles(db: Session, workspace_id: str) -> dict[str, str]:
    """Each member's role in the workspace, by user id."""
    return dict(db.execute(select(Membership.user_id, Membership.role).where(Membership.workspace_id == workspace_id)).all())


def summarize(db: Session, project: Project, document_count: int) -> ProjectSummary:
    """One project with its document count and the people shown on it."""
    people = _people(db, {project.lead_user_id, project.updated_by})
    return ProjectSummary(project, document_count, people.get(project.lead_user_id or ""), people.get(project.updated_by or ""))


def _touch(project: Project, principal: Principal) -> None:
    """Record that ``principal`` just changed something in the project."""
    project.updated_at = datetime.now(UTC)
    project.updated_by = principal.user_id


def list_members(db: Session, principal: Principal) -> list[tuple[Person, str]]:
    """Everyone in the caller's workspace, with their role, by name."""
    rows = db.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == principal.workspace_id)
    ).all()
    return sorted(((Person(u.id, u.name or u.email, u.email), role) for u, role in rows), key=lambda r: r[0].name.lower())


def _check_member(db: Session, principal: Principal, user_id: str) -> None:
    if db.get(Membership, (user_id, principal.workspace_id)) is None:
        raise NotFound("That person isn't in your workspace.")


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
    rows = db.execute(query).all()
    people = _people(db, {p.lead_user_id for p, _ in rows} | {p.updated_by for p, _ in rows})
    return [ProjectSummary(p, int(n), people.get(p.lead_user_id or ""), people.get(p.updated_by or "")) for p, n in rows]


def _ensure_unique_name(db: Session, principal: Principal, name: str, *, exclude_id: str | None = None) -> None:
    clash = db.scalar(select(Project).where(Project.workspace_id == principal.workspace_id, Project.name == name))
    if clash is not None and clash.id != exclude_id:
        raise Conflict(f"A project named '{name}' already exists.")


def create_project(
    db: Session, principal: Principal, *, name: str, client_name: str = "", folder: str = "", lead_user_id: str | None = None
) -> Project:
    """A new project. The creator is in charge unless someone else is named."""
    _ensure_unique_name(db, principal, name.strip())
    if lead_user_id:
        _check_member(db, principal, lead_user_id)
    project = Project(
        workspace_id=principal.workspace_id,
        name=name.strip(),
        client_name=(client_name or name).strip(),
        folder=folder.strip(),
        created_by=principal.user_id,
        lead_user_id=lead_user_id or principal.user_id,
        updated_by=principal.user_id,
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
    folder: str | None = None,
    lead_user_id: str | None = None,
    clear_lead: bool = False,
    archived: bool | None = None,
) -> Project:
    project = _get(db, principal, project_id)
    if name is not None:
        _ensure_unique_name(db, principal, name.strip(), exclude_id=project.id)
        project.name = name.strip()
    if client_name is not None:
        project.client_name = client_name.strip()
    if folder is not None:
        project.folder = folder.strip()
    if lead_user_id:
        _check_member(db, principal, lead_user_id)
        project.lead_user_id = lead_user_id
    elif clear_lead:
        project.lead_user_id = None
    if archived is not None:
        project.archived = archived
    _touch(project, principal)
    db.flush()
    return project


def delete_project(db: Session, blobs: BlobStore, principal: Principal, project_id: str) -> None:
    """Delete a project with all its saved work and library files. Allowed
    for workspace owners/admins, the person in charge, and its creator."""
    project = _get(db, principal, project_id)
    if not (principal.is_admin or principal.user_id in (project.created_by, project.lead_user_id)):
        raise Forbidden("Only the person in charge, the project's creator or a workspace admin can delete it.")
    keys = list(db.scalars(select(Document.storage_key).where(Document.project_id == project_id)))
    db.execute(delete(ProjectState).where(ProjectState.project_id == project_id))
    db.execute(delete(Document).where(Document.project_id == project_id))
    db.delete(project)
    db.flush()
    for key in keys:
        blobs.delete(key)


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
    _touch(project, principal)
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
    _touch(project, principal)
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
    project = _get(db, principal, project_id)
    document = db.get(Document, document_id)
    if document is None or document.project_id != project_id:
        raise NotFound("No such document in this project.")
    _touch(project, principal)
    db.delete(document)
    db.flush()
    blobs.delete(document.storage_key)
