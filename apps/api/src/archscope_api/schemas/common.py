"""Cross-cutting response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from .base import ApiModel


class Health(ApiModel):
    status: Literal["ok"]
    version: str
    environment: str


class Problem(ApiModel):
    """RFC 9457 problem details — the body of every error response."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(description="Stable URI identifying the problem kind; switch on this, not on `title`.")
    title: str
    status: int
    detail: str
    instance: str
    trace_id: str | None = None
    errors: list[dict[str, Any]] | None = Field(None, description="Per-field errors (validation-error only).")
