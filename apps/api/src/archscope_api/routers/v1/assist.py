"""Context-aware suggestions: each page's "Fill from earlier steps" /
"Suggest" button. The model reads the project context the page sends and
proposes values; only blanks are filled (see archscope_domain.assist)."""

from __future__ import annotations

from typing import Any

import anthropic
from fastapi import APIRouter
from google.genai import errors as genai_errors

from archscope_domain import assist

from ...problems import ProblemError
from ...schemas.assist import (
    ArchitectureAssistRequest,
    ArchitectureAssistResponse,
    ArchitectureInputs,
    AssistContext,
    CompanyOverview,
    CompanyOverviewRequest,
    CompanyOverviewResponse,
    ProjectTasksAssistRequest,
    ProjectTasksAssistResponse,
    ProposalAssistRequest,
    ProposalAssistResponse,
    StagePlannerAssistRequest,
    StagePlannerAssistResponse,
    SuggestedTask,
)
from ...schemas.proposal import ProposalDocument
from ...schemas.stage_planner import PlannedStage
from ...services import website
from ..deps import AiBackend, AiClientDep, SettingsDep, offload
from .discovery import _classify_gemini

router = APIRouter(prefix="/assist", tags=["assist"])

_NO_CONTEXT = "There's nothing to work from yet. Fill in the discovery call (or the Requirements Document) first, then try again."


def _context(body: AssistContext) -> dict[str, Any]:
    discovery = (
        assist.discovery_context(
            body.discovery.to_domain(), client_name=body.discovery.client_name, business_type=body.discovery.business_type
        )
        if body.discovery
        else None
    )
    context = assist.build_context(
        discovery=discovery,
        business_analysis=body.business_analysis,
        documents=body.documents,
        stage_planner=[s.model_dump() for s in body.stage_planner],
    )
    if not assist.has_context(context):
        raise ProblemError(422, "no-context", "Nothing to suggest from", _NO_CONTEXT)
    return context


def _ask(
    ai: AiBackend, anthropic_model: str | None, task: str, context: dict[str, Any], current: Any
) -> tuple[dict[str, Any], str]:
    """The model's suggestion and the model's name, with AI failures as problem responses."""
    try:
        if ai.provider == "gemini":
            return assist.ask_gemini(ai.client, task, context, current, models=ai.models, classify=_classify_gemini)
        return assist.ask_claude(ai.client, task, context, current, model=anthropic_model), anthropic_model or "Claude"
    except assist.AssistError as exc:
        raise ProblemError(502, "ai-incomplete", "No usable suggestions", str(exc)) from exc
    except anthropic.AuthenticationError as exc:
        raise ProblemError(
            503, "ai-not-configured", "AI credentials were rejected", "Check the Anthropic key under Settings."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise ProblemError(429, "ai-rate-limited", "AI rate limit reached", "Wait a minute and try again.") from exc
    except anthropic.APIError as exc:
        raise ProblemError(502, "ai-unavailable", "AI request failed", str(exc)) from exc
    except genai_errors.APIError as exc:
        if exc.code in (400, 401, 403) and "key" in str(exc).lower():
            raise ProblemError(
                503, "ai-not-configured", "AI credentials were rejected", "Check the Gemini key under Settings."
            ) from exc
        if exc.code == 429:
            raise ProblemError(
                429,
                "ai-rate-limited",
                "AI rate limit reached",
                "The Gemini free quota is used up for now. Wait a minute and try again.",
            ) from exc
        if exc.code in (500, 503, 504):
            raise ProblemError(
                503, "ai-busy", "The AI service is busy", "Every model we tried was busy. Wait a minute and try again."
            ) from exc
        raise ProblemError(502, "ai-unavailable", "AI request failed", str(exc)) from exc


@router.post(
    "/stage-planner", response_model=StagePlannerAssistResponse, summary="Fill the Deal Stage Planner from earlier steps"
)
async def stage_planner(body: StagePlannerAssistRequest, ai: AiClientDep, settings: SettingsDep) -> StagePlannerAssistResponse:
    context = _context(body.context)
    current = [s.model_dump() for s in body.stages]
    suggestion, model = await offload(_ask, ai, settings.anthropic_model, assist.STAGE_PLANNER, context, current)
    rows, filled = assist.merge_stages(current, suggestion)
    return StagePlannerAssistResponse(stages=[PlannedStage.model_validate(r) for r in rows], filled=filled, model=model)


@router.post(
    "/architecture",
    response_model=ArchitectureAssistResponse,
    summary="Fill the Architecture Generator's inputs from earlier steps",
)
async def architecture(body: ArchitectureAssistRequest, ai: AiClientDep, settings: SettingsDep) -> ArchitectureAssistResponse:
    context = _context(body.context)
    current = body.inputs.model_dump()
    suggestion, model = await offload(_ask, ai, settings.anthropic_model, assist.ARCHITECTURE, context, current)
    merged, added = assist.merge_architecture(current, suggestion)
    return ArchitectureAssistResponse(inputs=ArchitectureInputs.model_validate(merged), added=added, model=model)


@router.post("/proposal", response_model=ProposalAssistResponse, summary="Suggest proposal content from earlier steps")
async def proposal(body: ProposalAssistRequest, ai: AiClientDep, settings: SettingsDep) -> ProposalAssistResponse:
    context = _context(body.context)
    current = body.proposal.to_domain()
    suggestion, model = await offload(
        _ask, ai, settings.anthropic_model, assist.PROPOSAL, context, assist.proposal_brief(current)
    )
    merged, changed = assist.merge_proposal(current, suggestion)
    return ProposalAssistResponse(proposal=ProposalDocument.from_domain(merged), changed=changed, model=model)


@router.post(
    "/project-tasks", response_model=ProjectTasksAssistResponse, summary="Suggest follow-up tasks for each engagement stage"
)
async def project_tasks(body: ProjectTasksAssistRequest, ai: AiClientDep, settings: SettingsDep) -> ProjectTasksAssistResponse:
    context = _context(body.context)
    current = [t.model_dump() for t in body.tasks]
    suggestion, model = await offload(_ask, ai, settings.anthropic_model, assist.PROJECT_TASKS, context, current)
    return ProjectTasksAssistResponse(
        tasks=[SuggestedTask.model_validate(t) for t in assist.merge_tasks(current, suggestion)], model=model
    )


@router.post("/company-overview", response_model=CompanyOverviewResponse, summary="A company overview from the client's website")
async def company_overview(body: CompanyOverviewRequest, ai: AiClientDep, settings: SettingsDep) -> CompanyOverviewResponse:
    try:
        snapshot = await offload(website.read_homepage, body.website)
    except website.WebsiteError as exc:
        raise ProblemError(422, "website-unreadable", "The website couldn't be read", str(exc)) from exc
    context: dict[str, Any] = {"website": snapshot.excerpt()}
    client = {k: v for k, v in (("name", body.client_name.strip()), ("business_type", body.business_type.strip())) if v}
    if client:
        context["client_as_typed"] = client
    suggestion, model = await offload(_ask, ai, settings.anthropic_model, assist.COMPANY_OVERVIEW, context, None)
    return CompanyOverviewResponse(
        overview=CompanyOverview.model_validate(assist.clean_overview(suggestion)), website=snapshot.url, model=model
    )
