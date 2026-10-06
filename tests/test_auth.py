"""Login gate (core/auth.py) through the real entrypoint, Home.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.auth import _email_allowed, hash_password, verify_password

HOME = str(Path(__file__).resolve().parent.parent / "Home.py")


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED", raising=False)


def _home(**secrets) -> AppTest:
    at = AppTest.from_file(HOME)
    for key, value in secrets.items():
        at.secrets[key] = value
    at.run(timeout=20)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def test_hash_round_trip_and_plaintext():
    stored = hash_password("s3cret", iterations=1000)
    assert verify_password("s3cret", stored)
    assert not verify_password("wrong", stored)
    assert verify_password("plain", "plain")
    assert not verify_password("plain", "other")


def test_unconfigured_app_fails_closed():
    at = _home()
    assert any("isn't configured" in e.value for e in at.error)
    assert not any("Connect your API keys" in m.value for m in at.markdown)


def test_password_login_and_logout():
    at = _home(passwords={"aylin": hash_password("s3cret", iterations=1000)})
    assert not any("Connect your API keys" in m.value for m in at.markdown)

    at.text_input(key="_auth_username").input("aylin")
    at.text_input(key="_auth_password").input("wrong")
    at.button[0].click().run(timeout=20)
    assert any("Incorrect" in e.value for e in at.error)

    at.text_input(key="_auth_username").input("aylin")
    at.text_input(key="_auth_password").input("s3cret")
    at.button[0].click().run(timeout=20)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("Connect your API keys" in m.value for m in at.markdown)

    at.sidebar.button(key="_auth_logout").click().run(timeout=20)
    assert not any("Connect your API keys" in m.value for m in at.markdown)


def test_google_allowlist(monkeypatch):
    monkeypatch.setattr("core.auth._secret_section", lambda name: {
        "access": {"allowed_emails": ["Me@Gmail.com"], "allowed_domains": ["@sonamation.com"]},
    }.get(name, {}))
    assert _email_allowed("me@gmail.com")
    assert _email_allowed("anyone@sonamation.com")
    assert not _email_allowed("stranger@gmail.com")
    assert not _email_allowed(None)


def test_google_allowlist_empty_denies_everyone(monkeypatch):
    monkeypatch.setattr("core.auth._secret_section", lambda name: {})
    assert not _email_allowed("me@gmail.com")
