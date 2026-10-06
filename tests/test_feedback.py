"""In-app feedback: settings, email content, attachment limits, sending
(against a fake SMTP server — no network), and the floating widget."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import core.feedback as fb
from core.feedback import (
    DEFAULT_RECIPIENT,
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    Attachment,
    FeedbackError,
    MailSettings,
    build_message,
    load_settings,
    send,
)

HOME = str(Path(__file__).resolve().parent.parent / "Home.py")
SETTINGS = MailSettings("smtp.example.com", 587, "bot@sonamation.com", "app-password", "bot@sonamation.com", DEFAULT_RECIPIENT)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


# ---- settings ---------------------------------------------------------------------


def test_no_password_means_sending_is_off():
    assert load_settings({}, {}) is None
    assert load_settings({"feedback": {"smtp_username": "a@b.com"}}, {}) is None


def test_secrets_win_over_env_and_defaults_fill_in():
    s = load_settings(
        {"feedback": {"smtp_username": "bot@sonamation.com", "smtp_password": "pw"}},
        {"FEEDBACK_SMTP_USERNAME": "other@x.com", "FEEDBACK_SMTP_PASSWORD": "other"},
    )
    assert s == MailSettings("smtp.gmail.com", 587, "bot@sonamation.com", "pw", "bot@sonamation.com", DEFAULT_RECIPIENT, "starttls")


def test_env_fallback_and_port_465_defaults_to_ssl():
    s = load_settings({}, {"FEEDBACK_SMTP_USERNAME": "u@x.com", "FEEDBACK_SMTP_PASSWORD": "p", "FEEDBACK_SMTP_PORT": "465", "FEEDBACK_TO": "t@x.com"})
    assert (s.port, s.security, s.recipient) == (465, "ssl", "t@x.com")


# ---- message --------------------------------------------------------------------


def test_message_has_context_reply_to_and_attachments():
    msg = build_message(
        SETTINGS,
        kind="Bug",
        text="Generate does nothing",
        page="Discovery Call Assistant",
        user="maria@sonamation.com",
        attachments=[Attachment("screen.png", PNG)],
        sent_at=datetime(2026, 10, 6, 15, 30, tzinfo=timezone.utc),
    )
    assert msg["Subject"] == "[ArchitectureScope] Bug — Discovery Call Assistant — maria@sonamation.com"
    assert msg["To"] == DEFAULT_RECIPIENT
    assert msg["Reply-To"] == "maria@sonamation.com"
    body = msg.get_body(preferencelist=("plain",)).get_content()
    for expected in ["Type:     Bug", "Page:     Discovery Call Assistant", "2026-10-06 15:30 UTC", "Generate does nothing", "screen.png"]:
        assert expected in body
    (att,) = list(msg.iter_attachments())
    assert att.get_filename() == "screen.png"
    assert att.get_content_type() == "image/png"
    assert att.get_content() == PNG


def test_screenshot_only_feedback_is_allowed_and_no_reply_to_without_email():
    msg = build_message(SETTINGS, kind="Idea", text="", page="Setup", user=None, attachments=[Attachment("a.jpg", PNG)])
    assert "Reply-To" not in msg
    assert "(no text" in msg.get_body(preferencelist=("plain",)).get_content()


@pytest.mark.parametrize(
    ("text", "attachments", "error"),
    [
        ("   ", [], "Write a short description"),
        ("x" * 6000, [], "under 5000"),
        ("hi", [Attachment(f"{i}.png", PNG) for i in range(MAX_ATTACHMENTS + 1)], "at most"),
        ("hi", [Attachment("notes.exe", PNG)], "isn't a picture"),
        ("hi", [Attachment("big.png", b"0" * (MAX_ATTACHMENT_BYTES + 1))], "larger than"),
        ("hi", [Attachment(f"{i}.png", b"0" * (MAX_ATTACHMENT_BYTES - 10)) for i in range(3)], "add up to"),
    ],
)
def test_invalid_feedback_gets_a_friendly_error(text, attachments, error):
    with pytest.raises(FeedbackError, match=error):
        build_message(SETTINGS, kind="Bug", text=text, page="p", user=None, attachments=attachments)


# ---- sending ----------------------------------------------------------------------


class _FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls = host, port, []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, message):
        self.calls.append(("send", message["Subject"]))


@pytest.fixture
def fake_smtp(monkeypatch):
    _FakeSMTP.instances = []
    monkeypatch.setattr(fb.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(fb.smtplib, "SMTP_SSL", _FakeSMTP)
    return _FakeSMTP


def test_send_uses_starttls_then_login(fake_smtp):
    msg = build_message(SETTINGS, kind="Bug", text="x", page="p", user=None, attachments=[])
    send(SETTINGS, msg)
    (server,) = fake_smtp.instances
    assert server.calls == ["starttls", ("login", "bot@sonamation.com"), ("send", msg["Subject"])]


def test_auth_failure_becomes_friendly_error(monkeypatch):
    class Rejecting(_FakeSMTP):
        def login(self, user, password):
            raise fb.smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(fb.smtplib, "SMTP", Rejecting)
    with pytest.raises(FeedbackError, match="rejected its login"):
        send(SETTINGS, build_message(SETTINGS, kind="Bug", text="x", page="p", user=None, attachments=[]))


def test_unreachable_server_becomes_friendly_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(fb.smtplib, "SMTP", boom)
    with pytest.raises(FeedbackError, match="Couldn't reach"):
        send(SETTINGS, build_message(SETTINGS, kind="Bug", text="x", page="p", user=None, attachments=[]))


# ---- widget ------------------------------------------------------------------------


def _home() -> AppTest:
    at = AppTest.from_file(HOME)
    at.run(timeout=30)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def test_feedback_button_is_on_every_page():
    for page in ["app_pages/0_Setup.py", "app_pages/11_Discovery_Call_Assistant.py", "app_pages/9_Project_Library.py"]:
        at = _home()
        at.switch_page(page)
        at.run(timeout=30)
        assert not at.exception, [str(e) for e in at.exception]
        assert at.chat_input(key="feedback_input") is not None


def test_sending_text_feedback_emails_it_with_the_page(monkeypatch, fake_smtp):
    monkeypatch.setenv("FEEDBACK_SMTP_USERNAME", "bot@sonamation.com")
    monkeypatch.setenv("FEEDBACK_SMTP_PASSWORD", "app-password")
    at = _home()
    at.chat_input(key="feedback_input").set_value("The proposal PDF button does nothing").run(timeout=30)
    assert not at.exception, [str(e) for e in at.exception]
    (server,) = fake_smtp.instances
    assert server.calls[-1] == ("send", "[ArchitectureScope] Bug — Setup & API keys — unknown user")
    bubbles = [m.markdown[0].value for m in at.chat_message]
    assert any("The proposal PDF button does nothing" in b for b in bubbles)
    assert any("Sent" in b for b in bubbles)


def test_without_mail_settings_the_user_is_told_to_email(monkeypatch, fake_smtp):
    for var in ["FEEDBACK_SMTP_USERNAME", "FEEDBACK_SMTP_PASSWORD"]:
        monkeypatch.delenv(var, raising=False)
    at = _home()
    at.chat_input(key="feedback_input").set_value("hello").run(timeout=30)
    assert not fake_smtp.instances
    assert any(DEFAULT_RECIPIENT in m.markdown[0].value for m in at.chat_message)
