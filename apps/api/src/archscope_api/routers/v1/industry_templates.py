"""Industry templates: starting points for discovery and the proposal by
industry and company size. Applying one fills blanks only."""

from __future__ import annotations

from fastapi import APIRouter

from archscope_domain import industry_templates as it

from ...problems import ProblemError
from ...schemas.assist import (
    IndustryDiscoveryRequest,
    IndustryDiscoveryResponse,
    IndustryProposalRequest,
    IndustryProposalResponse,
    IndustryTemplates,
    TemplateChoice,
)
from ...schemas.discovery import DiscoveryNotes
from ...schemas.proposal import ProposalDocument
from ..deps import offload

router = APIRouter(prefix="/industry-templates", tags=["industry templates"])


def _unknown(exc: it.TemplateError) -> ProblemError:
    return ProblemError(422, "unknown-template", "Unknown template", str(exc))


@router.get("", response_model=IndustryTemplates, summary="The industries and company sizes available")
async def list_templates() -> IndustryTemplates:
    return IndustryTemplates(
        industries=[TemplateChoice(id=c.id, label=c.label, description=c.description) for c in it.industries()],
        sizes=[TemplateChoice(id=c.id, label=c.label, description=c.description) for c in it.sizes()],
    )


@router.post("/discovery", response_model=IndustryDiscoveryResponse, summary="Pre-fill unanswered discovery questions")
async def apply_to_discovery(body: IndustryDiscoveryRequest) -> IndustryDiscoveryResponse:
    try:
        notes, business_type, filled = await offload(
            it.apply_discovery, body.notes.to_domain(), body.notes.business_type, body.industry, body.size
        )
    except it.TemplateError as exc:
        raise _unknown(exc) from exc
    result = DiscoveryNotes.model_validate({**body.notes.model_dump(), "business_type": business_type, "sections": notes})
    return IndustryDiscoveryResponse(notes=result, filled=filled)


@router.post("/proposal", response_model=IndustryProposalResponse, summary="Add an industry template's rows to a proposal")
async def apply_to_proposal(body: IndustryProposalRequest) -> IndustryProposalResponse:
    try:
        merged, changed = await offload(it.apply_proposal, body.proposal.to_domain(), body.industry, body.size)
    except it.TemplateError as exc:
        raise _unknown(exc) from exc
    return IndustryProposalResponse(proposal=ProposalDocument.from_domain(merged), changed=changed)
