"""HTTP contract: health, RFC 9457 errors, request ids, CORS, SSE
streaming, and OpenAPI drift."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from google.genai import errors as genai_errors
from httpx import ASGITransport, AsyncClient

from archscope_api.main import create_app
from archscope_api.openapi import OPENAPI_PATH, render_openapi
from archscope_api.routers.deps import AiBackend, get_ai_client, get_portal_reader
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
    app = create_app(Settings(environment="production", secret_key="x" * 32))
    assert app.openapi_url is None
    assert app.docs_url is None


def test_production_refuses_to_start_without_a_secret_key() -> None:
    with pytest.raises(RuntimeError, match="ARCHSCOPE_SECRET_KEY"):
        create_app(Settings(environment="production", secret_key=None))


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

    return AiBackend("anthropic", SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))), calls


def _all_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """The document's events (``status`` progress notes left out)."""
    return [e for e in _all_events(body) if e[0] != "status"]


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


def _fake_gemini(per_model: dict[str, Any]) -> tuple[AiBackend, list[str]]:
    """A Gemini backend whose models either stream text or raise (e.g. a 429).
    A list of outcomes is consumed one per call (to fail, then succeed)."""
    tried: list[str] = []

    def generate_content_stream(**kwargs: Any) -> Any:
        tried.append(kwargs["model"])
        outcome = per_model[kwargs["model"]]
        if isinstance(outcome, list):
            outcome = outcome.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        content = SimpleNamespace(parts=[SimpleNamespace(text=outcome, thought=False)])
        return iter([SimpleNamespace(prompt_feedback=None, candidates=[SimpleNamespace(content=content, finish_reason="STOP")])])

    client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=generate_content_stream))
    return AiBackend("gemini", client, tuple(per_model)), tried


async def test_gemini_falls_back_to_the_next_model_when_quota_is_used_up(app: FastAPI) -> None:
    quota = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    ai, tried = _fake_gemini({"gemini-3.8-flash": quota, "gemini-2.5-pro": "# Drafted"})
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/client-explainer", json={"modules": ["Sales Hub"]})
    assert tried == ["gemini-3.8-flash", "gemini-2.5-pro"]
    assert _events(response.text) == [("delta", {"text": "# Drafted"}), ("done", {})]


async def test_gemini_quota_used_up_everywhere_is_a_rate_limit_error(app: FastAPI) -> None:
    quota = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    ai, tried = _fake_gemini({"gemini-3.8-flash": quota, "gemini-2.5-pro": quota})
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/client-explainer", json={"modules": ["Sales Hub"]})
    assert tried == ["gemini-3.8-flash", "gemini-2.5-pro"]
    ((event, problem),) = _events(response.text)
    assert event == "error"
    assert problem["type"].endswith("/ai-rate-limited")


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


def test_schema_names_are_unique() -> None:
    """Two API models with the same class name get module-qualified OpenAPI
    names, which breaks the web app's generated types — rename one instead."""
    names = json.loads(render_openapi())["components"]["schemas"]
    assert not [n for n in names if "__" in n], sorted(n for n in names if "__" in n)


def _busy() -> genai_errors.ServerError:
    return genai_errors.ServerError(
        503, {"error": {"code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE"}}
    )


async def test_busy_gemini_model_is_retried_then_replaced(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    from archscope_api.services import discovery as svc

    monkeypatch.setattr(svc, "RETRY_DELAYS", (0.0,))
    ai, tried = _fake_gemini({"gemini-3.8-flash": [_busy(), _busy()], "gemini-2.5-pro": "# Drafted"})
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/business-analysis", json={"client_name": "Acme"})
    assert tried == ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-2.5-pro"]
    assert _events(response.text) == [("delta", {"text": "# Drafted"}), ("done", {})]
    notes = [d["message"] for e, d in _all_events(response.text) if e == "status"]
    assert notes[0] == "Drafting with Gemini 3.8 Flash"
    assert any("busy" in n and "Gemini 2.5 Pro" in n for n in notes)


async def test_busy_gemini_recovers_on_retry(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    from archscope_api.services import discovery as svc

    monkeypatch.setattr(svc, "RETRY_DELAYS", (0.0,))
    ai, tried = _fake_gemini({"gemini-3.8-flash": [_busy(), "# Second try"], "gemini-2.5-pro": "unused"})
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/business-analysis", json={"client_name": "Acme"})
    assert tried == ["gemini-3.8-flash", "gemini-3.8-flash"]
    assert _events(response.text)[0] == ("delta", {"text": "# Second try"})


async def test_every_gemini_model_busy_is_a_friendly_error(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    from archscope_api.services import discovery as svc

    monkeypatch.setattr(svc, "RETRY_DELAYS", (0.0,))
    ai, _ = _fake_gemini({"gemini-3.8-flash": [_busy(), _busy()], "gemini-2.5-pro": [_busy(), _busy()]})
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/api/v1/discovery/business-analysis", json={"client_name": "Acme"})
    ((event, problem),) = _events(response.text)
    assert event == "error"
    assert problem["type"].endswith("/ai-busy")
    assert "wait a minute" in problem["detail"]


async def test_ai_models_lists_gemini_models_in_order(app: FastAPI) -> None:
    ai, _ = _fake_gemini({"gemini-3.8-flash": "x", "gemini-3.5-flash-lite": "y"})
    from archscope_api.routers.deps import find_ai_backend

    app.dependency_overrides[find_ai_backend] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        body = (await http.get("/api/v1/discovery/ai-models")).json()
    assert body["provider"] == "gemini"
    assert [(m["id"], m["label"]) for m in body["models"]] == [
        ("gemini-3.8-flash", "Gemini 3.8 Flash"),
        ("gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite"),
    ]
    assert body["models"][1]["note"] == "Fastest · least busy"


async def test_ai_models_without_a_key_is_none(app: FastAPI) -> None:
    from archscope_api.routers.deps import find_ai_backend

    app.dependency_overrides[find_ai_backend] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/api/v1/discovery/ai-models")).json() == {"provider": "none", "models": []}


async def test_chosen_model_is_tried_first_then_the_rest(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    from archscope_api.services import discovery as svc

    monkeypatch.setattr(svc, "RETRY_DELAYS", (0.0,))
    ai, tried = _fake_gemini(
        {"gemini-3.8-flash": "unused", "gemini-3.5-flash-lite": [_busy(), _busy()], "gemini-3.6-flash": "# From 3.6"}
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post(
            "/api/v1/discovery/business-analysis?model=gemini-3.5-flash-lite", json={"client_name": "Acme"}
        )
        unknown = await http.post("/api/v1/discovery/business-analysis?model=gpt-9", json={"client_name": "Acme"})
    assert tried[:3] == ["gemini-3.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
    assert _events(response.text)[0] == ("delta", {"text": "unused"})
    assert unknown.status_code == 422
