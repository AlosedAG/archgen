"""Accounts, projects, the project library, and workspace settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .base import ApiModel


class SignInRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=500)


class Me(ApiModel):
    """The signed-in user and their workspace."""

    user_id: str
    email: str
    name: str
    workspace_id: str
    workspace_name: str
    role: str
    is_admin: bool


class AuthConfig(ApiModel):
    """Which sign-in methods the server offers."""

    password: bool = True
    google: bool = False
    signup: bool = Field(False, description="People can create their own account (email confirmed with a code).")
    password_reset: bool = False
    email_delivery: str = Field("none", description='"smtp", "outbox" (local development: codes are logged), or "none".')
    min_password_length: int = 10


class SignUpRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=500)


class EmailOnly(ApiModel):
    email: str = Field(min_length=3, max_length=320)


class CodeConfirm(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordResetConfirm(CodeConfirm):
    password: str = Field(min_length=1, max_length=500)


class Accepted(ApiModel):
    message: str


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    client_name: str = Field("", max_length=200)


class ProjectUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    client_name: str | None = Field(None, max_length=200)
    archived: bool | None = None


class Project(ApiModel):
    id: str
    name: str
    client_name: str
    archived: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class ModuleState(ApiModel):
    """A module's saved working state for a project. Send back the
    ``version`` you loaded when saving; a newer saved version is a 409."""

    module: str
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(0, description="0 = nothing saved yet.")
    updated_at: datetime | None = None


class ModuleStateSave(ApiModel):
    data: dict[str, Any]
    version: int = Field(ge=0, description="The version this edit was based on.")


class Document(ApiModel):
    id: str
    document_type: str
    title: str
    filename: str
    media_type: str
    size_bytes: int
    created_at: datetime


class SecretStatus(ApiModel):
    """A stored credential's status — never its value."""

    name: str
    label: str
    configured: bool
    hint: str = Field("", description="Last 4 characters, to recognise which key is stored.")
    updated_at: datetime | None = None


class SecretSet(ApiModel):
    value: str = Field(min_length=8, max_length=2000)
