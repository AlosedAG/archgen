"""Self sign-up and password reset with emailed 6-digit codes."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.mail import OutboxMailer
from archscope_api.main import create_app
from archscope_api.persistence.db import session_scope
from archscope_api.persistence.models import EmailCode
from archscope_api.routers.deps import get_mailer, get_settings
from archscope_api.services import signup
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings

PASSWORD = "a long enough passphrase"


@pytest.fixture
def outbox(tmp_path) -> OutboxMailer:  # type: ignore[no-untyped-def]
    return OutboxMailer(tmp_path / "outbox")


@pytest.fixture
async def http(settings: Settings, principal: Principal, outbox: OutboxMailer):  # type: ignore[no-untyped-def]
    app: FastAPI = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_mailer] = lambda: outbox
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _code(outbox: OutboxMailer) -> str:
    match = re.search(r"Your code: (\d{6})", outbox.sent[-1].text)
    assert match, outbox.sent[-1].text
    return match.group(1)


def _age_last_send(settings: Settings, email: str, purpose: str) -> None:
    """Pretend the last code went out over a minute ago (skip the resend throttle)."""
    with session_scope(settings.database_url) as db:
        record = db.get(EmailCode, (email, purpose))
        assert record is not None
        record.last_sent_at = datetime.now(UTC) - timedelta(minutes=2)


async def test_config_offers_signup_with_outbox_in_dev(http: AsyncClient) -> None:
    body = (await http.get("/api/v1/auth/config")).json()
    assert body["signup"] is True
    assert body["password_reset"] is True
    assert body["email_delivery"] == "outbox"


async def test_signup_emails_a_code_and_verifying_creates_the_account(http: AsyncClient, outbox: OutboxMailer) -> None:
    response = await http.post("/api/v1/auth/sign-up", json={"name": "Bo", "email": "Bo@Example.com", "password": PASSWORD})
    assert response.status_code == 202
    assert outbox.sent[-1].to == "bo@example.com"
    code = _code(outbox)
    # Not an account yet.
    assert (await http.post("/api/v1/auth/sign-in", json={"email": "bo@example.com", "password": PASSWORD})).status_code == 401

    verified = await http.post("/api/v1/auth/sign-up/verify", json={"email": "bo@example.com", "code": code})
    assert verified.status_code == 200
    me = verified.json()
    assert (me["email"], me["name"], me["role"], me["workspace_name"]) == ("bo@example.com", "Bo", "owner", "Bo's workspace")
    assert "archscope_session=" in verified.headers["set-cookie"]
    assert (await http.get("/api/v1/auth/me")).json()["email"] == "bo@example.com"
    # The code is single-use.
    again = await http.post("/api/v1/auth/sign-up/verify", json={"email": "bo@example.com", "code": code})
    assert again.status_code == 400


async def test_signup_domain_joins_the_existing_workspace(
    http: AsyncClient, outbox: OutboxMailer, settings: Settings, principal: Principal
) -> None:
    with session_scope(settings.database_url) as db:
        signup.set_signup_domains(db, "SonaMation", ["SonaMation.com"])
    await http.post("/api/v1/auth/sign-up", json={"name": "Cy", "email": "cy@sonamation.com", "password": PASSWORD})
    me = (await http.post("/api/v1/auth/sign-up/verify", json={"email": "cy@sonamation.com", "code": _code(outbox)})).json()
    assert (me["workspace_id"], me["role"]) == (principal.workspace_id, "member")


async def test_wrong_codes_are_limited(http: AsyncClient, outbox: OutboxMailer) -> None:
    await http.post("/api/v1/auth/sign-up", json={"name": "D", "email": "d@example.com", "password": PASSWORD})
    right = _code(outbox)
    wrong = "000000" if right != "000000" else "111111"
    for left in (4, 3, 2, 1):
        response = await http.post("/api/v1/auth/sign-up/verify", json={"email": "d@example.com", "code": wrong})
        assert response.status_code == 400
        assert f"{left} attempt" in response.json()["detail"]
    await http.post("/api/v1/auth/sign-up/verify", json={"email": "d@example.com", "code": wrong})
    locked = await http.post("/api/v1/auth/sign-up/verify", json={"email": "d@example.com", "code": right})
    assert locked.status_code == 400
    assert "Ask for a new one" in locked.json()["detail"]


async def test_expired_code_is_refused(http: AsyncClient, outbox: OutboxMailer, settings: Settings) -> None:
    await http.post("/api/v1/auth/sign-up", json={"name": "E", "email": "e@example.com", "password": PASSWORD})
    code = _code(outbox)
    with session_scope(settings.database_url) as db:
        record = db.get(EmailCode, ("e@example.com", "signup"))
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    response = await http.post("/api/v1/auth/sign-up/verify", json={"email": "e@example.com", "code": code})
    assert "expired" in response.json()["detail"]


async def test_resend_is_throttled_and_replaces_the_code(http: AsyncClient, outbox: OutboxMailer, settings: Settings) -> None:
    await http.post("/api/v1/auth/sign-up", json={"name": "F", "email": "f@example.com", "password": PASSWORD})
    first = _code(outbox)
    assert (await http.post("/api/v1/auth/sign-up/resend", json={"email": "f@example.com"})).status_code == 429
    _age_last_send(settings, "f@example.com", "signup")
    assert (await http.post("/api/v1/auth/sign-up/resend", json={"email": "f@example.com"})).status_code == 202
    second = _code(outbox)
    if second != first:
        old = await http.post("/api/v1/auth/sign-up/verify", json={"email": "f@example.com", "code": first})
        assert old.status_code == 400
    assert (await http.post("/api/v1/auth/sign-up/verify", json={"email": "f@example.com", "code": second})).status_code == 200


async def test_existing_email_gets_a_notice_not_a_code(http: AsyncClient, outbox: OutboxMailer, principal: Principal) -> None:
    response = await http.post("/api/v1/auth/sign-up", json={"name": "X", "email": principal.email, "password": PASSWORD})
    assert response.status_code == 202  # same as a new email: nothing revealed
    assert outbox.sent[-1].subject == "You already have an ArchitectureScope account"
    assert "Your code" not in outbox.sent[-1].text


@pytest.mark.parametrize(
    ("password", "expected"),
    [("short", "at least 10"), ("g@example.com", "email address"), ("aaaaaaaaaaaa", "mix of characters")],
)
async def test_weak_passwords_are_refused(http: AsyncClient, password: str, expected: str) -> None:
    response = await http.post("/api/v1/auth/sign-up", json={"name": "G", "email": "g@example.com", "password": password})
    assert response.status_code == 422
    assert expected in response.json()["detail"]


async def test_password_reset_signs_out_other_sessions(
    http: AsyncClient, outbox: OutboxMailer, principal: Principal, test_password: str, settings: Settings
) -> None:
    other = AsyncClient(transport=http._transport, base_url="http://test")  # a second browser
    await other.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    assert (await other.get("/api/v1/auth/me")).status_code == 200

    assert (await http.post("/api/v1/auth/password-reset", json={"email": "nobody@example.com"})).status_code == 202
    sent_before = len(outbox.sent)
    assert (await http.post("/api/v1/auth/password-reset", json={"email": principal.email})).status_code == 202
    assert len(outbox.sent) == sent_before + 1
    new_password = "a brand new passphrase"
    confirmed = await http.post(
        "/api/v1/auth/password-reset/confirm", json={"email": principal.email, "code": _code(outbox), "password": new_password}
    )
    assert confirmed.status_code == 200
    assert (await other.get("/api/v1/auth/me")).status_code == 401
    old = await http.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    assert old.status_code == 401
    assert (await http.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": new_password})).status_code == 200
    await other.aclose()


async def test_signup_is_off_without_email_outside_dev(tmp_path, principal: Principal) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(
        environment="staging",
        secret_key="x" * 32,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        blob_dir=str(tmp_path / "blobs"),
        ANTHROPIC_API_KEY=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/auth/config")).json()["signup"] is False
        response = await client.post("/api/v1/auth/sign-up", json={"name": "H", "email": "h@example.com", "password": PASSWORD})
        assert response.status_code == 503
