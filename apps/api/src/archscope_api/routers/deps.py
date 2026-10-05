"""FastAPI dependencies and response helpers shared by every router."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Any

import anthropic
from fastapi import Depends, Response
from fastapi.security import APIKeyHeader
from starlette.concurrency import run_in_threadpool

from archscope_domain.ports import PortalReader
from archscope_integrations.hubspot import HubSpotClient

from ..problems import ProblemError
from ..settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def offload[**P, R](fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """Run blocking / CPU-bound domain work in the threadpool so the event
    loop keeps serving other requests (SSE streams, health checks)."""
    return await run_in_threadpool(fn, *args, **kwargs)


# ---- HubSpot -------------------------------------------------------------
# Phase 1: the caller supplies a private-app token per request. Phase 2
# replaces this with the organization's encrypted stored credential; the
# dependency's signature (-> PortalReader) stays the same.

_hubspot_token = APIKeyHeader(
    name="X-HubSpot-Token",
    scheme_name="HubSpotToken",
    description="HubSpot private app access token (read-only scopes). Never stored or logged.",
    auto_error=False,
)


def get_portal_reader(token: Annotated[str | None, Depends(_hubspot_token)]) -> PortalReader:
    if not token:
        raise ProblemError(
            400, "hubspot-token-required", "HubSpot token required", "Send a private app token in the X-HubSpot-Token header."
        )
    return HubSpotClient(token)


PortalReaderDep = Annotated[PortalReader, Depends(get_portal_reader)]


# ---- Anthropic -----------------------------------------------------------


def get_ai_client(settings: SettingsDep) -> Any:
    if settings.anthropic_api_key is None:
        raise ProblemError(503, "ai-not-configured", "AI drafting is not configured", "Set ANTHROPIC_API_KEY on the API server.")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())


AiClientDep = Annotated[Any, Depends(get_ai_client)]


# ---- binary responses ----------------------------------------------------

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "png": "image/png",
    "dot": "text/vnd.graphviz; charset=utf-8",
    "drawio": "application/vnd.jgraph.mxfile",
}


def file_response(content: bytes, *, stem: str, ext: str) -> Response:
    """A download with a safe filename and the correct media type."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "document"
    return Response(
        content=content,
        media_type=MEDIA_TYPES[ext],
        headers={"Content-Disposition": f'attachment; filename="{safe}.{ext}"'},
    )


def binary_responses(*exts: str) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses=`` entry documenting a file download."""
    return {200: {"content": {MEDIA_TYPES[e]: {"schema": {"type": "string", "format": "binary"}} for e in exts}}}
