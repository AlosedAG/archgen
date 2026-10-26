"""Database tables (SQLAlchemy 2.0, typed). Portable across PostgreSQL
(production) and SQLite (local development, tests).

Tenancy: every project, document and stored credential belongs to a
workspace (the consultancy); users join workspaces through memberships
with a role. Ids are UUID strings so they're safe to expose in URLs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, false
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """A timezone-aware timestamp that always reads back as UTC. SQLite
    stores no offset, so without this its values come back naive and
    clients would read them as local time."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    # Email domains whose self-signed-up users join this workspace (e.g. ["sonamation.com"]).
    signup_domains: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    # Set once Hubzy's default questions have been copied in, so deleting them all doesn't bring them back.
    hubzy_seeded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Same for the standard SOW clauses.
    clauses_seeded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    # pbkdf2_sha256$iterations$salt$digest; None for Google-only accounts.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)

    memberships: Mapped[list[Membership]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_MEMBER)

    user: Mapped[User] = relationship(back_populates="memberships")
    workspace: Mapped[Workspace] = relationship()


class AuthSession(Base):
    """A signed-in browser. The id is the SHA-256 of the cookie token, so a
    database leak doesn't hand out live sessions."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class Project(Base):
    """A client engagement. Every module's work and saved documents hang off it."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_project_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    client_name: Mapped[str] = mapped_column(String(200), default="")
    # A free-text folder for grouping projects (e.g. one per client); "" = none.
    folder: Mapped[str] = mapped_column(String(120), default="", server_default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Who is in charge of the engagement (any workspace member), and who last changed anything in it.
    lead_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)


class ProposalTemplate(Base):
    """A proposal / SOW saved by a team member for reuse with a similar
    client — shared with the whole workspace."""

    __tablename__ = "proposal_templates"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_proposal_template_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(500), default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)


class ProjectState(Base):
    """One module's working state for a project (e.g. the Discovery call
    notes), as JSON. ``version`` increments on every save so concurrent
    editors can't silently overwrite each other."""

    __tablename__ = "project_states"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    module: Mapped[str] = mapped_column(String(50), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class Document(Base):
    """A file saved to a project's library. Bytes live in the blob store under ``storage_key``."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(150))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)


class StoredFile(Base):
    """A library file's bytes, when files are kept in the database
    (ARCHSCOPE_BLOB_STORE=database) — for hosts whose disk doesn't
    survive restarts, like Cloud Run."""

    __tablename__ = "stored_files"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class WorkspaceSecret(Base):
    """An encrypted credential (Fernet) — the HubSpot token, the Anthropic key."""

    __tablename__ = "workspace_secrets"

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    # Last 4 characters, to show which key is stored without revealing it.
    hint: Mapped[str] = mapped_column(String(8), default="")
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


PURPOSE_SIGNUP = "signup"
PURPOSE_RESET = "reset"


class EmailCode(Base):
    """A pending email confirmation: a sign-up waiting for its code, or a
    password reset. Only an HMAC of the code is stored."""

    __tablename__ = "email_codes"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(20), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    # Sign-up details held until the code is confirmed (name, password hash).
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_sent_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class HubzyTopic(Base):
    """A question Hubzy, the in-app assistant, can answer, with his answer.
    Each workspace has its own list, edited by its admins. ``page`` limits a
    topic to one page (the last part of its URL); "" shows it everywhere."""

    __tablename__ = "hubzy_topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    page: Mapped[str] = mapped_column(String(80), default="")
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SowClause(Base):
    """One clause of the workspace's standard SOW terms: boilerplate the firm
    owns, edited by its admins, copied into every new SOW (where it can be
    switched off or edited for that deal). ``key`` matches a SOW's copy back
    to its library clause."""

    __tablename__ = "sow_clauses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    include_by_default: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class WorkspaceState(Base):
    """A workspace-wide tool's saved working state (e.g. the Leads or
    Integrations tracker), as JSON; versioned like ``ProjectState``."""

    __tablename__ = "workspace_states"

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    module: Mapped[str] = mapped_column(String(50), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
