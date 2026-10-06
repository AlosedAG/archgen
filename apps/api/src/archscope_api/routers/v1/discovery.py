"""Discovery Call Assistant (Module 11).

AI drafts stream as Server-Sent Events so the browser renders text as the
model writes it. Event types:

- ``delta`` — ``{"text": "..."}``, a chunk of the document
- ``done``  — ``{}``, the document finished normally
- ``error`` — an RFC 9457 problem object; sent mid-stream because a
  refusal / truncation is only known after the text has streamed
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import anthropic
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from archscope_domain.discovery import DiscoveryError

from ...problems import TYPE_BASE
from ...schemas.discovery import (
    AnalysisPayload,
    ClientExplainerRequest,
    DiscoveryNotes,
    QuestionBank,
    SuggestModulesRequest,
    SuggestModulesResponse,
)
from ...services import discovery
from ..deps import AiClientDep, SettingsDep, offload

router = APIRouter(prefix="/discovery", tags=["discovery"])

_SSE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"description": "Server-Sent Events: `delta`, then `done` or `error`.", "content": {"text/event-stream": {}}}
}


@router.get("/question-bank", response_model=QuestionBank, summary="The configured discovery questions")
async def question_bank() -> QuestionBank:
    return QuestionBank.from_domain(await offload(discovery.question_bank))


@router.post("/business-analysis/payload", response_model=AnalysisPayload, summary="Preview the exact AI request payload")
async def business_analysis_payload(body: DiscoveryNotes) -> AnalysisPayload:
    payload = await offload(
        discovery.business_analysis_payload, body.to_domain(), client_name=body.client_name, business_type=body.business_type
    )
    return AnalysisPayload.model_validate(payload)


@router.post(
    "/business-analysis", response_class=StreamingResponse, responses=_SSE_RESPONSES, summary="Draft the business analysis (SSE)"
)
async def business_analysis(
    body: DiscoveryNotes, request: Request, client: AiClientDep, settings: SettingsDep
) -> StreamingResponse:
    payload = await offload(
        discovery.business_analysis_payload, body.to_domain(), client_name=body.client_name, business_type=body.business_type
    )
    return _sse(discovery.stream_document(client, payload, model=settings.anthropic_model), request)


@router.post(
    "/client-explainer", response_class=StreamingResponse, responses=_SSE_RESPONSES, summary="Draft the client explainer (SSE)"
)
async def client_explainer(
    body: ClientExplainerRequest, request: Request, client: AiClientDep, settings: SettingsDep
) -> StreamingResponse:
    payload = discovery.client_explainer_payload(list(body.modules), business_type=body.business_type)
    return _sse(discovery.stream_document(client, payload, model=settings.anthropic_model), request)


@router.post("/suggest-modules", response_model=SuggestModulesResponse, summary="Hubs recommended by a business analysis")
async def suggest_modules(body: SuggestModulesRequest) -> SuggestModulesResponse:
    return SuggestModulesResponse.model_validate({"modules": discovery.suggest_modules(body.business_analysis_markdown)})


# ---- SSE framing -----------------------------------------------------------


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _problem(request: Request, status: int, slug: str, title: str, detail: str) -> dict[str, Any]:
    return {
        "type": TYPE_BASE + slug,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "trace_id": getattr(request.state, "request_id", None),
    }


def _sse(chunks: Iterator[str], request: Request) -> StreamingResponse:
    """Frame a (blocking) text iterator as SSE. Starlette iterates sync
    generators in the threadpool, so the model stream never blocks the loop."""

    def events() -> Iterator[str]:
        try:
            for text in chunks:
                yield _event("delta", {"text": text})
        except DiscoveryError as exc:
            yield _event("error", _problem(request, 502, "ai-incomplete", "The document was not completed", str(exc)))
            return
        except anthropic.AuthenticationError:
            yield _event(
                "error", _problem(request, 503, "ai-not-configured", "AI credentials were rejected", "Check ANTHROPIC_API_KEY.")
            )
            return
        except anthropic.RateLimitError:
            yield _event("error", _problem(request, 429, "ai-rate-limited", "AI rate limit reached", "Wait a minute and retry."))
            return
        except anthropic.APIError as exc:
            yield _event("error", _problem(request, 502, "ai-unavailable", "AI request failed", str(exc)))
            return
        yield _event("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
