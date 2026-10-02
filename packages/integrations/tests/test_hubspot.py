"""HubSpot adapter: conforms to the domain's read-only port, cannot write,
and maps HubSpot failures onto the port's errors. No network access."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from archscope_domain.ports import PortalAPIError, PortalReader, PortalScopeError
from archscope_integrations import hubspot
from archscope_integrations.hubspot import HubSpotClient


class _FakeResponse:
    def __init__(self, status: int, payload: Any = None, headers: dict[str, str] | None = None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload
        self.content = b"x" if payload is not None else b""
        self.text = str(payload)
        self.headers = headers or {}

    def json(self) -> Any:
        return self._payload


class _GetOnlySession:
    """Records GETs; any other verb fails the test."""

    def __init__(self, responses: list[_FakeResponse]):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, **_: Any) -> _FakeResponse:
        self.calls.append(url)
        return self.responses.pop(0)

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"HubSpotClient used session.{name} — only GET is allowed")


def _client(responses: list[_FakeResponse]) -> tuple[HubSpotClient, _GetOnlySession]:
    client = HubSpotClient("test-token")
    session = _GetOnlySession(responses)
    client._session = session  # type: ignore[assignment]
    return client, session


def test_conforms_to_the_domain_port() -> None:
    assert isinstance(HubSpotClient("t"), PortalReader)


def test_public_surface_is_read_only() -> None:
    """Every public method is a read. A create/update/delete method
    appearing here is a breach of the app's read-only guarantee."""
    public = {name for name, _ in inspect.getmembers(HubSpotClient, inspect.isfunction) if not name.startswith("_")}
    assert public
    assert all(name.startswith("get_") for name in public), public
    assert not hasattr(HubSpotClient, "_request")


def test_requires_explicit_token() -> None:
    with pytest.raises(ValueError):
        HubSpotClient("")


def test_get_retries_on_429_then_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hubspot.time, "sleep", lambda _s: None)
    client, session = _client([_FakeResponse(429, headers={"Retry-After": "0"}), _FakeResponse(200, {"workflows": [{"id": 1}]})])
    assert client.get_workflows() == [{"id": 1}]
    assert len(session.calls) == 2


def test_get_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hubspot.time, "sleep", lambda _s: None)
    client, _ = _client([_FakeResponse(429) for _ in range(hubspot.MAX_RETRIES + 1)])
    with pytest.raises(PortalAPIError, match="Rate limited"):
        client.get_workflows()


@pytest.mark.parametrize(("status", "error"), [(401, PortalScopeError), (403, PortalScopeError), (404, PortalAPIError), (500, PortalAPIError)])
def test_http_failures_map_to_port_errors(status: int, error: type[Exception]) -> None:
    client, _ = _client([_FakeResponse(status, {"message": "nope"})])
    with pytest.raises(error):
        client.get_workflow_detail(7)


def test_teams_missing_feature_is_empty_not_an_error() -> None:
    client, _ = _client([_FakeResponse(404, {})])
    assert client.get_teams() == []


def test_sdk_errors_map_to_port_errors() -> None:
    client = HubSpotClient("t")

    def scope_failure() -> None:
        raise _SdkError(403)

    with pytest.raises(PortalScopeError):
        client._call_with_retry(scope_failure)


def test_sdk_pipelines_404_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HubSpotClient("t")

    def missing(**_: Any) -> None:
        raise _SdkError(404)

    monkeypatch.setattr(client, "_sdk", SimpleNamespace(crm=SimpleNamespace(pipelines=SimpleNamespace(pipelines_api=SimpleNamespace(get_all=missing)))))
    assert client.get_pipelines("2-123") == []


class _SdkError(Exception):
    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.headers: dict[str, str] = {}
