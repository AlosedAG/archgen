"""In-app feedback (bug reports, ideas, questions) contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import ApiModel


class FeedbackAttachment(ApiModel):
    filename: str = Field(max_length=200)
    content_type: str = Field(pattern=r"^image/[a-z0-9.+-]+$", description="Screenshots only (image/png, image/jpeg, …).")
    data: str = Field(description="The file, base64-encoded.")


class FeedbackRequest(ApiModel):
    kind: Literal["bug", "idea", "question"]
    message: str = Field("", max_length=5000)
    page: str = Field("", max_length=200, description="The page's title, e.g. 'Proposal & SOW Builder'.")
    path: str = Field("", max_length=300, description="The page's URL path.")
    project_name: str = Field("", max_length=200)
    attachments: list[FeedbackAttachment] = Field(default_factory=list, max_length=5)
