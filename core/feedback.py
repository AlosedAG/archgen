"""In-app feedback: turns a user's message + screenshots into an email to
the app owner and sends it over SMTP.

Kept free of Streamlit so it's unit-testable; the floating chat widget
that collects the feedback lives in ``core/feedback_ui.py``.

Configuration comes from the app's secrets (``[feedback]`` section, see
``.streamlit/secrets.toml.example``) or, as a fallback, environment
variables ``FEEDBACK_SMTP_HOST`` / ``_PORT`` / ``_USERNAME`` /
``_PASSWORD`` and ``FEEDBACK_TO`` / ``FEEDBACK_FROM``. With no SMTP
password configured the widget still opens, but tells the user to email
instead of pretending the message was sent.
"""

from __future__ import annotations

import mimetypes
import smtplib
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any

DEFAULT_RECIPIENT = "aylin@sonamation.com"
FEEDBACK_KINDS = ["Bug", "Idea", "Question"]

ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf")
MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024  # per file
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # stays under Gmail's 25 MB message limit
MAX_MESSAGE_CHARS = 5000


class FeedbackError(RuntimeError):
    """Feedback couldn't be sent; the message is safe to show the user."""


@dataclass(frozen=True)
class MailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipient: str
    # "starttls" (default), "ssl" (implicit TLS, usually port 465), or
    # "none" — plain SMTP, only for a local test relay such as MailHog.
    security: str = "starttls"


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes


def load_settings(secrets: Mapping[str, Any], env: Mapping[str, str]) -> MailSettings | None:
    """Mail settings from ``secrets["feedback"]`` (preferred) or env vars.
    ``None`` when no SMTP password is configured — sending is then disabled."""
    section = secrets.get("feedback", {}) if secrets else {}

    def pick(key: str, env_key: str, default: str = "") -> str:
        value = section.get(key) if hasattr(section, "get") else None
        return str(value if value not in (None, "") else env.get(env_key, default)).strip()

    password = pick("smtp_password", "FEEDBACK_SMTP_PASSWORD")
    username = pick("smtp_username", "FEEDBACK_SMTP_USERNAME")
    if not password or not username:
        return None
    try:
        port = int(pick("smtp_port", "FEEDBACK_SMTP_PORT", "587"))
    except ValueError:
        port = 587
    security = pick("smtp_security", "FEEDBACK_SMTP_SECURITY", "ssl" if port == 465 else "starttls").lower()
    if security not in {"starttls", "ssl", "none"}:
        security = "starttls"
    return MailSettings(
        host=pick("smtp_host", "FEEDBACK_SMTP_HOST", "smtp.gmail.com"),
        port=port,
        username=username,
        password=password,
        sender=pick("from", "FEEDBACK_FROM", username),
        recipient=pick("to", "FEEDBACK_TO", DEFAULT_RECIPIENT),
        security=security,
    )


def validate_attachments(attachments: list[Attachment]) -> None:
    """Raise :class:`FeedbackError` (with a user-facing message) if the
    files can't be emailed: too many, too big, or not an image/PDF."""
    if len(attachments) > MAX_ATTACHMENTS:
        raise FeedbackError(f"Please attach at most {MAX_ATTACHMENTS} files.")
    total = 0
    for att in attachments:
        if not att.filename.lower().endswith(ALLOWED_EXTENSIONS):
            raise FeedbackError(f"“{att.filename}” isn't a picture or PDF. Attach screenshots (PNG/JPG) or a PDF.")
        if len(att.content) > MAX_ATTACHMENT_BYTES:
            raise FeedbackError(f"“{att.filename}” is larger than {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")
        total += len(att.content)
    if total > MAX_TOTAL_BYTES:
        raise FeedbackError(f"The attachments add up to more than {MAX_TOTAL_BYTES // (1024 * 1024)} MB. Send fewer or smaller screenshots.")


def build_message(
    settings: MailSettings,
    *,
    kind: str,
    text: str,
    page: str,
    user: str | None,
    attachments: list[Attachment],
    sent_at: datetime | None = None,
) -> EmailMessage:
    """The feedback email: a scannable subject, the context the owner
    needs to reproduce the problem, the user's words, and the screenshots.
    Reply-To is the user, so answering them is one click."""
    text = text.strip()
    if not text and not attachments:
        raise FeedbackError("Write a short description or attach a screenshot first.")
    if len(text) > MAX_MESSAGE_CHARS:
        raise FeedbackError(f"Please keep the message under {MAX_MESSAGE_CHARS} characters.")
    validate_attachments(attachments)

    sent_at = sent_at or datetime.now(timezone.utc)
    who = user or "unknown user"
    msg = EmailMessage()
    msg["Subject"] = f"[ArchitectureScope] {kind} — {page or 'unknown page'} — {who}"
    msg["From"] = settings.sender
    msg["To"] = settings.recipient
    if user and "@" in user:
        msg["Reply-To"] = user
    msg["Message-ID"] = make_msgid(domain="architecturescope")
    msg.set_content(
        "\n".join(
            [
                f"Type:     {kind}",
                f"From:     {who}",
                f"Page:     {page or 'unknown'}",
                f"Sent:     {sent_at.strftime('%Y-%m-%d %H:%M UTC')}",
                f"Files:    {', '.join(a.filename for a in attachments) or 'none'}",
                "",
                "Message:",
                text or "(no text — see attached screenshots)",
            ]
        )
    )
    for att in attachments:
        mime, _ = mimetypes.guess_type(att.filename)
        maintype, subtype = (mime or "application/octet-stream").split("/", 1)
        msg.add_attachment(att.content, maintype=maintype, subtype=subtype, filename=att.filename)
    return msg


def send(settings: MailSettings, message: EmailMessage, *, timeout: float = 20.0) -> None:
    """Send over SMTP using ``settings.security``. Raises
    :class:`FeedbackError` with a user-safe message on failure."""
    context = ssl.create_default_context()
    try:
        if settings.security == "ssl":
            with smtplib.SMTP_SSL(settings.host, settings.port, timeout=timeout, context=context) as server:
                server.login(settings.username, settings.password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.host, settings.port, timeout=timeout) as server:
                if settings.security == "starttls":
                    server.starttls(context=context)
                    server.login(settings.username, settings.password)
                server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise FeedbackError("The feedback mailbox rejected its login. Please email your feedback instead.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise FeedbackError("Couldn't reach the mail server. Please try again in a minute, or email your feedback instead.") from exc
