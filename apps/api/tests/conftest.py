"""API test harness: an isolated app per test (with its own SQLite
database and a seeded workspace + user), an async HTTP client over ASGI
(no network, no server), the Streamlit-era golden fixtures, and an
in-memory read-only portal.

``client`` is signed in as the seeded user (the principal dependency is
overridden); ``anon_client`` isn't, for testing sign-in itself."""

from __future__ import annotations

import json
import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.main import create_app
from archscope_api.persistence.db import get_engine, session_scope
from archscope_api.persistence.models import Base
from archscope_api.persistence.security import hash_password
from archscope_api.routers.deps import current_principal, get_portal_reader
from archscope_api.services import auth
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings, get_settings

TEST_EMAIL = "ana@sonamation.test"
TEST_PASSWORD = "correct horse battery staple"

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "packages" / "domain" / "tests" / "golden" / "fixtures"


class InMemoryPortalReader:
    """A read-only portal with canned records. Implements PortalReader."""

    def __init__(
        self,
        records: dict[str, list[dict[str, Any]]] | None = None,
        associations: dict[tuple[str, str], dict[str, list[str]]] | None = None,
    ):
        self.records = records or {}
        self.associations = associations or {}

    def get_custom_object_schemas(self) -> list[dict[str, Any]]:
        return []

    def get_properties(self, object_type: str) -> list[dict[str, Any]]:
        return [
            {
                "name": "email",
                "label": "Email",
                "type": "string",
                "field_type": "text",
                "group_name": "contactinformation",
                "hubspot_defined": True,
            }
        ]

    def get_pipelines(self, object_type: str) -> list[dict[str, Any]]:
        return []

    def get_owners(self) -> list[dict[str, Any]]:
        return [{"id": "1", "email": "a@x.com", "first_name": "A", "last_name": "B", "teams": [], "archived": False}]

    def get_teams(self) -> list[dict[str, Any]]:
        return []

    def get_workflows(self) -> list[dict[str, Any]]:
        return []

    def get_workflow_detail(self, workflow_id: Any) -> dict[str, Any]:
        return {}

    def get_records_sample(self, object_type: str, limit: int = 100, properties: list[str] | None = None) -> list[dict[str, Any]]:
        return list(self.records.get(object_type, []))[:limit]

    def get_associations_sample(self, from_object_type: str, to_object_type: str, object_ids: list[str]) -> dict[str, list[str]]:
        full = self.associations.get((from_object_type, to_object_type), {})
        return {oid: ids for oid, ids in full.items() if oid in object_ids}


PORTAL = InMemoryPortalReader(
    records={
        "contacts": [
            {"id": "1", "properties": {"email": "a@x.com", "lifecyclestage": "Lead"}},
            {"id": "2", "properties": {"email": "b@x.com"}},
            {"id": "3", "properties": {"email": "", "lifecyclestage": "Customer"}},
        ],
    },
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        ANTHROPIC_API_KEY=None,
        cors_origins=["http://localhost:3000"],
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        blob_dir=str(tmp_path / "blobs"),
    )


@pytest.fixture(scope="session")
def schema_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty database with the full schema, built once and copied per test
    (creating tables per test is slow on Windows file systems)."""
    path = tmp_path_factory.mktemp("schema") / "template.db"
    engine = get_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return path


@pytest.fixture
def principal(settings: Settings, schema_template: Path) -> Principal:
    """A fresh database with one workspace owner, signed in for ``client``."""
    shutil.copyfile(schema_template, settings.database_url.removeprefix("sqlite:///"))
    with session_scope(settings.database_url) as db:
        user = auth.create_user(db, email=TEST_EMAIL, name="Ana", workspace_name="SonaMation", role="owner")
        # A cheap hash keeps the suite fast; production uses 600k iterations.
        user.password_hash = hash_password(TEST_PASSWORD, iterations=1_000)
        membership = user.memberships[0]
        return Principal(user.id, user.email, user.name, membership.workspace_id, "SonaMation", "owner")


@pytest.fixture
def app(settings: Settings, principal: Principal) -> FastAPI:
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_portal_reader] = lambda: PORTAL
    application.dependency_overrides[current_principal] = lambda: principal
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
async def anon_client(settings: Settings, principal: Principal) -> AsyncIterator[AsyncClient]:
    """No signed-in user: the real session-cookie check applies."""
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_portal_reader] = lambda: PORTAL
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as http:
        yield http


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def portal_reader() -> InMemoryPortalReader:
    return PORTAL


@pytest.fixture(scope="session")
def golden() -> Callable[[str], Any]:
    """Load a golden fixture captured from the Streamlit-era code."""

    def load(name: str) -> Any:
        return json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return load


@pytest.fixture
def test_password() -> str:
    """The seeded user's password (their email is ``principal.email``)."""
    return TEST_PASSWORD
