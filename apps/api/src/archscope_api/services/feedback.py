"""In-app feedback: a user's bug report, idea or question (with optional
screenshots) emailed to the app owner, with who sent it and from where."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime

from ..mail import Attachment, Mailer, Message
from .auth import Principal
from .errors import InvalidInput

MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024
# Base64 adds a third, and requests through the web app's proxy must stay under ~10 MB.
MAX_TOTAL_BYTES = 6 * 1024 * 1024
KIND_LABELS = {"bug": "Bug", "idea": "Idea", "question": "Question"}


def decode_attachments(raw: list[tuple[str, str, str]]) -> tuple[Attachment, ...]:
    """``(filename, content_type, base64 data)`` → attachments, within the size limits."""
    out: list[Attachment] = []
    total = 0
    for filename, content_type, data in raw:
        try:
            content = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidInput(f"'{filename}' couldn't be read. Attach it again.") from exc
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise InvalidInput(f"'{filename}' is larger than {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")
        total += len(content)
        out.append(Attachment(filename=filename or "screenshot.png", content_type=content_type, data=content))
    if total > MAX_TOTAL_BYTES:
        raise InvalidInput(
            f"The screenshots add up to more than {MAX_TOTAL_BYTES // (1024 * 1024)} MB. Send fewer or smaller ones."
        )
    return tuple(out)


def send_feedback(
    mailer: Mailer,
    principal: Principal,
    *,
    to: str,
    kind: str,
    message: str,
    page: str,
    path: str,
    project_name: str,
    attachments: tuple[Attachment, ...],
) -> None:
    """Email the feedback to ``to``. Replies go straight to the sender."""
    message = message.strip()
    if not message and not attachments:
        raise InvalidInput("Write what happened, or attach a screenshot.")
    label = KIND_LABELS.get(kind, "Feedback")
    first_line = message.splitlines()[0][:70] if message else "(screenshot only)"
    where = page or path or "the app"
    body = "\n".join(
        [
            f"{label} from {principal.name or principal.email} <{principal.email}>",
            f"Workspace: {principal.workspace_name}",
            f"Page: {where}" + (f" ({path})" if path and path != where else ""),
            *([f"Project: {project_name}"] if project_name else []),
            f"Sent: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Screenshots: {len(attachments)}",
            "",
            message or "(no message — see the screenshots)",
        ]
    )
    mailer.send(
        Message(
            to=to,
            subject=f"[ArchitectureScope {label}] {where} — {first_line}",
            text=body,
            attachments=attachments,
            reply_to=principal.email,
        )
    )
