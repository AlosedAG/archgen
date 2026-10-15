"""In-app feedback: the Feedback button's bug reports, ideas and questions,
emailed to the app owner."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.feedback import FeedbackRequest
from ...schemas.workspace import Accepted
from ...services import feedback
from ...services.errors import Unavailable
from ..deps import MailerDep, PrincipalDep, SettingsDep, offload

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=Accepted, status_code=202, summary="Send a bug report, idea or question to the app owner")
async def send_feedback(body: FeedbackRequest, principal: PrincipalDep, settings: SettingsDep, mailer: MailerDep) -> Accepted:
    if mailer is None:
        raise Unavailable(f"Feedback email isn't set up on this server yet. Please email {settings.feedback_to} instead.")
    attachments = feedback.decode_attachments([(a.filename, a.content_type, a.data) for a in body.attachments])
    await offload(
        feedback.send_feedback,
        mailer,
        principal,
        to=settings.feedback_to,
        kind=body.kind,
        message=body.message,
        page=body.page,
        path=body.path,
        project_name=body.project_name,
        attachments=attachments,
    )
    return Accepted(message="Thanks! Your feedback was sent.")
