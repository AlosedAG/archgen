"""Reading a client's homepage for the business analysis: what's extracted,
the guard against non-public addresses, redirects and failures, and how a
draft uses it (status notes; a site that can't be read never fails it)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.routers.deps import get_ai_client
from archscope_api.routers.v1 import discovery as discovery_router
from archscope_api.services import website
from archscope_api.services.website import WebsiteError, normalize_url, parse_homepage, read_homepage

HTML = """<!doctype html><html><head><title>Bright Smiles Dental | Family dentistry</title>
<meta name="description" content="Three clinics in Toronto. Book online in minutes.">
<script src="https://js.hs-scripts.com/123.js"></script><script>var secret = "not text";</script>
<link href="https://assets.calendly.com/x.css"></head>
<body><nav>Home</nav><h1>Healthy smiles for the whole family</h1>
<p>We run three clinics across Toronto.</p><h2>Book online</h2><p>We run three clinics across Toronto.</p>
<style>.x{}</style></body></html>"""


def test_parse_homepage_extracts_title_description_text_and_tech() -> None:
    snap = parse_homepage("https://brightsmiles.example", HTML)
    assert snap.title == "Bright Smiles Dental | Family dentistry"
    assert snap.description.startswith("Three clinics in Toronto")
    assert snap.headings == ["Healthy smiles for the whole family", "Book online"]
    assert "not text" not in snap.text  # scripts are skipped
    assert snap.text.count("three clinics") == 1  # repeated text de-duplicated
    assert snap.technologies == ["HubSpot", "Calendly"]
    excerpt = snap.excerpt()
    assert "Technology seen in the page source: HubSpot, Calendly" in excerpt


def test_urls_are_normalized_and_only_http_allowed() -> None:
    assert normalize_url("acme.com") == "https://acme.com"
    with pytest.raises(WebsiteError):
        normalize_url("ftp://acme.com")
    with pytest.raises(WebsiteError):
        normalize_url("   ")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "10.0.0.8", "169.254.169.254", "192.168.1.1"])
def test_non_public_addresses_are_refused(host: str) -> None:
    with pytest.raises(WebsiteError, match="public"):
        read_homepage(f"http://{host}/")


def _client(routes: dict[str, httpx.Response]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_redirects_are_followed_and_errors_reported() -> None:
    client = _client(
        {
            "https://acme.example": httpx.Response(301, headers={"location": "https://www.acme.example/"}),
            "https://www.acme.example/": httpx.Response(200, headers={"content-type": "text/html"}, text=HTML),
            "https://down.example": httpx.Response(503),
        }
    )
    snap = read_homepage("acme.example", client=client, check_host=False)
    assert snap.url == "https://www.acme.example/"
    assert "Bright Smiles" in snap.title
    with pytest.raises(WebsiteError, match="503"):
        read_homepage("down.example", client=client, check_host=False)


# ---- In a draft ---------------------------------------------------------------------------------


def _fake_anthropic(calls: list[dict[str, Any]]) -> Any:
    from types import SimpleNamespace

    from archscope_api.routers.deps import AiBackend

    class Stream:
        text_stream = iter(["# Done"])

        def __enter__(self) -> Stream:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def get_final_message(self) -> Any:
            return SimpleNamespace(stop_reason="end_turn")

    def stream(**kwargs: Any) -> Stream:
        calls.append(kwargs)
        return Stream()

    return AiBackend("anthropic", SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream))))


def _sent_payload(call: dict[str, Any]) -> dict[str, Any]:
    return json.loads(call["messages"][0]["content"].split("\n\n", 1)[0])


async def test_draft_reads_the_website_first(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    app.dependency_overrides[get_ai_client] = lambda: _fake_anthropic(calls)
    monkeypatch.setattr(discovery_router, "_read_website", lambda url: f"URL: {url}\nTitle: Bright Smiles")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post(
            "/api/v1/discovery/business-analysis", json={"client_name": "Bright Smiles", "client_website": "brightsmiles.example"}
        )
    assert "Reading the client's website" in response.text
    client = _sent_payload(calls[0])["client"]
    assert client["website"] == "brightsmiles.example"
    assert "Title: Bright Smiles" in client["website_excerpt"]


async def test_unreadable_website_never_fails_the_draft(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    app.dependency_overrides[get_ai_client] = lambda: _fake_anthropic(calls)

    def boom(url: str) -> str:
        raise website.WebsiteError("The website took too long to answer.")

    monkeypatch.setattr(discovery_router, "_read_website", boom)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post(
            "/api/v1/discovery/business-analysis", json={"client_name": "A", "client_website": "slow.example"}
        )
    assert "event: done" in response.text
    assert "continuing without it" in response.text
    assert "took too long" in _sent_payload(calls[0])["client"]["website_excerpt"]
