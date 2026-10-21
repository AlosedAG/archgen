"""Hubzy, the in-app assistant: the questions he offers and his answers."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

from .base import ApiModel

PageKey = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80, pattern=r"^[a-z0-9-]*$")]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class HubzyTopic(ApiModel):
    """A question Hubzy can answer, and his answer."""

    id: str
    page: str = Field("", description='The page it shows on (the last part of its URL, e.g. "discovery"); "" = every page.')
    question: str
    answer: str


class HubzyTopicIn(ApiModel):
    id: str | None = Field(None, description="The row's id; omit for a new row.")
    page: PageKey = ""
    question: Question
    answer: Answer


class HubzyTopicsSave(ApiModel):
    """The whole edited table, in order. Rows left out are deleted."""

    topics: list[HubzyTopicIn] = Field(max_length=300)
