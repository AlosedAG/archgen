"""Outgoing email. SMTP in real environments; in local development and
tests, an outbox that writes each message to a file (and logs it) so
sign-up works without a mail server. The lowest API layer, beside
persistence."""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

log = logging.getLogger("archscope_api.mail")


@dataclass(frozen=True)
class Attachment:
    filename: str
    content_type: str  # e.g. "image/png"
    data: bytes


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    attachments: tuple[Attachment, ...] = ()
    reply_to: str | None = None


class Mailer(Protocol):
    def send(self, message: Message) -> None: ...


class SmtpMailer:
    def __init__(self, *, host: str, port: int, username: str | None, password: str, sender: str, security: str = "starttls"):
        self.host, self.port, self.username, self.password = host, port, username, password
        self.sender, self.security = sender, security

    def send(self, message: Message) -> None:
        email = EmailMessage()
        email["From"] = f"ArchitectureScope <{self.sender}>"
        email["To"] = message.to
        email["Subject"] = message.subject
        if message.reply_to:
            email["Reply-To"] = message.reply_to
        email.set_content(message.text)
        for attachment in message.attachments:
            maintype, _, subtype = attachment.content_type.partition("/")
            email.add_attachment(
                attachment.data,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )
        context = ssl.create_default_context()
        if self.security == "ssl":
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=20) as smtp:
                smtp.login(self.username or self.sender, self.password)
                smtp.send_message(email)
            return
        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            if self.security == "starttls":
                smtp.starttls(context=context)
            if self.security != "none":
                smtp.login(self.username or self.sender, self.password)
            smtp.send_message(email)


class OutboxMailer:
    """Development only: messages land in files under ``directory`` and the
    log, never on the network."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.sent: list[Message] = []

    def send(self, message: Message) -> None:
        self.sent.append(message)
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        safe_to = "".join(c if c.isalnum() or c in "@._-" else "_" for c in message.to)
        (self.directory / f"{stamp}_{safe_to}.txt").write_text(
            f"To: {message.to}\nSubject: {message.subject}\n\n{message.text}\n", encoding="utf-8"
        )
        for i, attachment in enumerate(message.attachments, 1):
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in attachment.filename)[:80]
            (self.directory / f"{stamp}_{safe_to}_{i}_{safe_name}").write_bytes(attachment.data)
        log.warning("Email (outbox, not sent) to %s — %s\n%s", message.to, message.subject, message.text)
