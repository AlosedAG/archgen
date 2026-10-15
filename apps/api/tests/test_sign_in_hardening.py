"""Sign-in hardening: repeated wrong passwords are throttled, unknown and
real emails take the same time, and self sign-up can be limited to the
company's email domain."""

from __future__ import annotations

import time

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.main import create_app
from archscope_api.routers.deps import get_mailer, get_settings
from archscope_api.services import auth
from archscope_api.services.auth import Principal
from archscope_api.settings import Settings


async def test_repeated_wrong_passwords_are_throttled(anon_client: AsyncClient, principal: Principal, test_password: str) -> None:
    for _ in range(auth.MAX_FAILED_SIGN_INS):
        wrong = await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": "wrong-password-1"})
        assert wrong.status_code == 401
    blocked = await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    assert blocked.status_code == 429
    assert "Forgot password" in blocked.json()["detail"]
    # Other accounts are unaffected.
    other = await anon_client.post("/api/v1/auth/sign-in", json={"email": "someone.else@example.test", "password": "x" * 12})
    assert other.status_code == 401


async def test_a_successful_sign_in_resets_the_count(anon_client: AsyncClient, principal: Principal, test_password: str) -> None:
    for _ in range(auth.MAX_FAILED_SIGN_INS - 1):
        await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": "wrong-password-1"})
    assert (
        await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    ).status_code == 200
    assert not auth._failures.get(principal.email)


def test_unknown_emails_cost_a_real_password_check() -> None:
    from archscope_api.persistence.security import _HASH_ITERATIONS

    assert f"${_HASH_ITERATIONS}$" in auth._timing_equalizer()


async def test_sign_up_can_be_limited_to_company_domains(settings: Settings, principal: Principal, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from archscope_api.mail import OutboxMailer

    limited = settings.model_copy(update={"signup_allowed_domains": "sonamation.com, @partner.example"})
    assert limited.signup_domains_allowed == ["sonamation.com", "partner.example"]
    app: FastAPI = create_app(limited)
    app.dependency_overrides[get_settings] = lambda: limited
    app.dependency_overrides[get_mailer] = lambda: OutboxMailer(tmp_path / "outbox")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        body = {"name": "Eve", "password": "a-long-password-1"}
        outsider = await http.post("/api/v1/auth/sign-up", json={**body, "email": "eve@gmail.com"})
        assert outsider.status_code == 403
        assert "@sonamation.com" in outsider.json()["detail"]
        insider = await http.post("/api/v1/auth/sign-up", json={**body, "email": "ana@SonaMation.com"})
        assert insider.status_code == 202


def test_throttle_window_expires() -> None:
    auth._failures["a@b.c"] = __import__("collections").deque([time.monotonic() - auth.FAILED_SIGN_IN_WINDOW - 1] * 9)
    assert len(auth._recent_failures("a@b.c", time.monotonic())) == 0


async def test_a_password_reset_lifts_the_lock(
    anon_client: AsyncClient, settings: Settings, principal: Principal, test_password: str
) -> None:
    from archscope_api.persistence.db import session_scope

    for _ in range(auth.MAX_FAILED_SIGN_INS):
        await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": "wrong-password-1"})
    with session_scope(settings.database_url) as db:
        auth.set_password(db, principal.email, "a-brand-new-password-1")
    fresh = await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": "a-brand-new-password-1"})
    assert fresh.status_code == 200
