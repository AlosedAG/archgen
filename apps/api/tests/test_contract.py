"""HTTP contract: health, RFC 9457 errors, request ids, CORS, SSE
streaming, and OpenAPI drift."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.main import create_app
from archscope_api.openapi import OPENAPI_PATH, render_openapi
from archscope_api.routers.deps import get_ai_client, get_portal_reader
from archscope_api.settings import Settings, get_settings
from archscope_domain.ports import PortalAPIError, PortalScopeError

PROBLEM = "application/problem+json"


async def test_health(client: AsyncClient) -> None:
    for path in ("/healthz", "/readyz"):
        response = await client.get(path)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["environment"] == "test"


async def test_request_id_is_echoed_or_assigned(client: AsyncClient) -> None:
    echoed = await client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assigned = await client.get("/healthz")
    assert echoed.headers["x-request-id"] == "abc123"
    assert len(assigned.headers["x-request-id"]) == 32


async def test_validation_errors_are_problem_json(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/blueprints", json={"project_name": "", "unknown_field": 1}, headers={"X-Request-ID": "r1"}
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["type"].endswith("/validation-error")
    assert body["trace_id"] == "r1"
    assert {tuple(e["loc"]) for e in body["errors"]} == {("body", "project_name"), ("body", "unknown_field")}


async def test_unknown_route_is_problem_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["type"].endswith("/not-found")


async def test_missing_hubspot_token_is_a_clear_problem(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_portal_reader)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/portal/snapshot")
    assert response.status_code == 400
    assert response.json()["type"].endswith("/hubspot-token-required")


@pytest.mark.parametrize(
    ("error", "slug"), [(PortalScopeError("403"), "hubspot-access-denied"), (PortalAPIError("boom"), "hubspot-unavailable")]
)
async def test_portal_errors_map_to_bad_gateway(app: FastAPI, error: Exception, slug: str) -> None:
    @app.get("/boom")
    async def boom() -> None:
        raise error

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/boom")
    assert response.status_code == 502
    assert response.json()["type"].endswith(slug)


async def test_unhandled_errors_do_not_leak_details(app: FastAPI) -> None:
    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret internals")

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as http:
        response = await http.get("/crash")
    assert response.status_code == 500
    assert "secret" not in response.text


async def test_ai_not_configured_is_503(client: AsyncClient) -> None:
    response = await client.post("/api/v1/discovery/client-explainer", json={"modules": ["Sales Hub"]})
    assert response.status_code == 503
    assert response.json()["type"].endswith("/ai-not-configured")


async def test_cors_allows_the_web_origin_only(client: AsyncClient) -> None:
    ok = await client.options(
        "/api/v1/blueprints", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    )
    bad = await client.options(
        "/api/v1/blueprints", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers


def test_docs_disabled_in_production() -> None:
    app = create_app(Settings(environment="production"))
    assert app.openapi_url is None
    assert app.docs_url is None


# ---- SSE -------------------------------------------------------------------------


class _FakeStream:
    def __init__(self, chunks: list[str], stop_reason: str):
        self.text_stream = iter(chunks)
        self._stop_reason = stop_reason

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> Any:
        return SimpleNamespace(stop_reason=self._stop_reason)


def _fake_ai(chunks: list[str], stop_reason: str = "end_turn") -> tuple[Any, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def stream(**kwargs: Any) -> _FakeStream:
        calls.append(kwargs)
        return _FakeStream(chunks, stop_reason)

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream))), calls


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def test_business_analysis_streams_sse(app: FastAPI) -> None:
    ai, calls = _fake_ai(["# Discovery\n", "Body"])
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/business-analysis", json={"client_name": "Acme"})
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _events(response.text) == [("delta", {"text": "# Discovery\n"}), ("delta", {"text": "Body"}), ("done", {})]
    sent = json.loads(calls[0]["messages"][0]["content"].split("\n\n", 1)[0])
    assert sent["mode"] == "business_analysis"
    assert sent["client"]["name"] == "Acme"


async def test_truncated_document_ends_with_error_event(app: FastAPI) -> None:
    ai, _ = _fake_ai(["partial"], stop_reason="max_tokens")
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/client-explainer", json={"modules": ["Sales Hub"]})
    events = _events(response.text)
    assert events[0] == ("delta", {"text": "partial"})
    assert events[-1][0] == "error"
    assert events[-1][1]["type"].endswith("/ai-incomplete")


async def test_model_override_from_settings(app: FastAPI) -> None:
    ai, calls = _fake_ai(["x"])
    app.dependency_overrides[get_ai_client] = lambda: ai
    app.dependency_overrides[get_settings] = lambda: Settings(environment="test", ANTHROPIC_MODEL="claude-sonnet-5-5")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        await http.post("/api/v1/discovery/client-explainer", json={"modules": ["Sales Hub"]})
    assert calls[0]["model"] == "claude-sonnet-5-5"


# ---- OpenAPI contract --------------------------------------------------------------


def test_openapi_is_committed_and_current() -> None:
    """The committed spec is the contract the TS client is generated from.
    Regenerate with: python -m archscope_api.openapi"""
    assert Path(OPENAPI_PATH).is_file(), "run: python -m archscope_api.openapi"
    assert json.loads(Path(OPENAPI_PATH).read_text(encoding="utf-8")) == json.loads(render_openapi())


def test_every_operation_is_documented() -> None:
    spec = json.loads(render_openapi())
    operation_ids = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("summary"), f"{method.upper()} {path} has no summary"
            operation_ids.append(op["operationId"])
    assert len(operation_ids) == len(set(operation_ids))
