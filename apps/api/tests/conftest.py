"""API test harness: an isolated app per test, an async HTTP client over
ASGI (no network, no server), the Streamlit-era golden fixtures, and an
in-memory read-only portal."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.main import create_app
from archscope_api.routers.deps import get_portal_reader
from archscope_api.settings import Settings, get_settings

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
def settings() -> Settings:
    return Settings(environment="test", ANTHROPIC_API_KEY=None, cors_origins=["http://localhost:3000"])


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_portal_reader] = lambda: PORTAL
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
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
