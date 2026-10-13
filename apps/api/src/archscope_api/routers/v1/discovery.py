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
from google.genai import errors as genai_errors

from archscope_domain.discovery import DiscoveryError
from archscope_domain.stage_planner import StagePlanner

from ...problems import TYPE_BASE
from ...schemas.discovery import (
    AnalysisPayload,
    BuildOrder,
    BuildOrderSettings,
    BuildSectionInfo,
    ClientExplainerRequest,
    DiscoveryConfig,
    DiscoveryNotes,
    EvaluateRequest,
    Evaluation,
    FlaggedTask,
    FollowUpQuestion,
    QuestionBank,
    RequiredTask,
    SuggestModulesRequest,
    SuggestModulesResponse,
)
from ...schemas.exports import ExportSection
from ...services import discovery, stage_planner
from ..deps import AiBackend, AiClientDep, SettingsDep, offload

router = APIRouter(prefix="/discovery", tags=["discovery"])

_SSE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"description": "Server-Sent Events: `delta`, then `done` or `error`.", "content": {"text/event-stream": {}}}
}


@router.get("/question-bank", response_model=QuestionBank, summary="The configured discovery questions")
async def question_bank() -> QuestionBank:
    return QuestionBank.from_domain(await offload(discovery.question_bank))


@router.get("/config", response_model=DiscoveryConfig, summary="Questions, follow-ups, tasks and build-order settings")
async def config() -> DiscoveryConfig:
    build = await offload(discovery.build_order_config)
    rules = build.checklist.rules
    return DiscoveryConfig(
        question_bank=QuestionBank.from_domain(rules.bank),
        follow_ups=[
            FollowUpQuestion(
                id=q.key,
                label=q.label,
                hint=q.hint,
                input=q.input,
                options=list(q.options),
                home_section=rules.home_sections[q.key],
            )
            for q in rules.follow_ups.values()
        ],
        tasks=[RequiredTask(id=t.key, label=t.label, detail=t.detail) for t in rules.tasks.values()],
        build_order=BuildOrderSettings(
            project_types=build.project_types,
            statuses=build.statuses,
            done_status=build.done_status,
            sections=[BuildSectionInfo(id=s.key, title=s.title) for s in build.sections],
            templates=build.templates,
        ),
    )


@router.post("/evaluate", response_model=Evaluation, summary="Follow-ups, required tasks, checklist and build order")
async def evaluate(body: EvaluateRequest) -> Evaluation:
    extra_items = (
        stage_planner.build_items(StagePlanner.from_dict({"stages": [s.model_dump() for s in body.stage_planner]}))
        if body.stage_planner
        else []
    )
    result = await offload(
        discovery.evaluate,
        body.to_domain(),
        client_name=body.client_name,
        project_type=body.project_type,
        done_build_items=body.done_build_items,
        extra_items=extra_items,
    )
    order = result.build_order
    return Evaluation(
        follow_ups={anchor: [q.key for q in qs] for anchor, qs in result.evaluation.follow_ups.items()},
        revealed_by={fid: list(options) for fid, options in result.evaluation.revealed_by.items()},
        tasks=[
            FlaggedTask(
                task=RequiredTask(id=t.task.key, label=t.task.label, detail=t.task.detail),
                section=t.section,
                reasons=list(t.reasons),
            )
            for t in result.evaluation.tasks
        ],
        checklist=[ExportSection(title=title, rows=rows) for title, rows in result.checklist],
        build_order=BuildOrder.model_validate(order.to_dict()),
        build_order_sections=[ExportSection(title=title, rows=rows) for title, rows in order.to_sections()],
    )


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
    return _sse(_draft(client, payload, settings.anthropic_model), request)


@router.post(
    "/client-explainer", response_class=StreamingResponse, responses=_SSE_RESPONSES, summary="Draft the client explainer (SSE)"
)
async def client_explainer(
    body: ClientExplainerRequest, request: Request, client: AiClientDep, settings: SettingsDep
) -> StreamingResponse:
    payload = discovery.client_explainer_payload(list(body.modules), business_type=body.business_type)
    return _sse(_draft(client, payload, settings.anthropic_model), request)


@router.post("/suggest-modules", response_model=SuggestModulesResponse, summary="Hubs recommended by a business analysis")
async def suggest_modules(body: SuggestModulesRequest) -> SuggestModulesResponse:
    return SuggestModulesResponse.model_validate({"modules": discovery.suggest_modules(body.business_analysis_markdown)})


# ---- Model call ------------------------------------------------------------


def _gemini_falls_back(exc: Exception) -> bool:
    """Per-model Gemini errors worth trying the next model for: free quota
    used up (429) or the model not available to this key (404)."""
    return isinstance(exc, genai_errors.ClientError) and exc.code in (404, 429)


def _draft(ai: AiBackend, payload: dict[str, Any], anthropic_model: str | None) -> Iterator[str]:
    if ai.provider == "gemini":
        return discovery.stream_document_gemini(ai.client, payload, models=ai.models, should_fall_back=_gemini_falls_back)
    return discovery.stream_document(ai.client, payload, model=anthropic_model)


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


def _gemini_problem(request: Request, exc: genai_errors.APIError) -> dict[str, Any]:
    if exc.code in (400, 401, 403) and "key" in str(exc).lower():
        return _problem(
            request, 503, "ai-not-configured", "AI credentials were rejected", "Check the Gemini API key under Settings."
        )
    if exc.code == 429:
        return _problem(
            request,
            429,
            "ai-rate-limited",
            "AI rate limit reached",
            "The Gemini free-tier quota is used up for every configured model. Wait a minute, or until the daily reset "
            "(midnight Pacific), and retry.",
        )
    return _problem(request, 502, "ai-unavailable", "AI request failed", str(exc))


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
        except genai_errors.APIError as exc:
            yield _event("error", _gemini_problem(request, exc))
            return
        yield _event("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
