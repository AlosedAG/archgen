"""Proposal & SOW Builder (Module 10). Stateless in Phase 1: the client
holds the document and posts it back; Phase 2 persists versions."""

from __future__ import annotations

from fastapi import APIRouter, Response

from ...schemas.proposal import (
    AddLibraryAddonsRequest,
    AddLibraryItemsRequest,
    CoverageRow,
    JepImportRequest,
    PricingSummary,
    ProposalAnalysis,
    ProposalDocument,
    ProposalLibraries,
    ProposalRequest,
    ScopeRow,
    WrdImportRequest,
)
from ...services import proposals
from ..deps import binary_responses, file_response, offload

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("/default", response_model=ProposalDocument, summary="A new proposal with standard boilerplate")
async def default_proposal() -> ProposalDocument:
    return ProposalDocument.from_domain(proposals.default_proposal())


@router.get("/libraries", response_model=ProposalLibraries, summary="Reusable scope items and add-on services")
async def libraries() -> ProposalLibraries:
    return ProposalLibraries.from_domain()


@router.post("/analysis", response_model=ProposalAnalysis, summary="Pricing, requirement coverage, scope groups and warnings")
async def analyse(body: ProposalRequest) -> ProposalAnalysis:
    result = await offload(proposals.analyse, body.proposal.to_domain())
    return ProposalAnalysis(
        pricing=PricingSummary.model_validate(result.pricing),
        coverage=[CoverageRow.from_domain(row) for row in result.coverage],
        scope_by_status={status: [ScopeRow.from_row(r) for r in rows] for status, rows in result.scope_by_status.items()},
        warnings=result.warnings,
    )


@router.post("/import/wrd", response_model=ProposalDocument, summary="Merge a Requirements Document into the proposal")
async def import_wrd(body: WrdImportRequest) -> ProposalDocument:
    return ProposalDocument.from_domain(await offload(proposals.import_wrd, body.proposal.to_domain(), body.wrd))


@router.post("/import/jep", response_model=ProposalDocument, summary="Merge a Joint Evaluation Plan into the proposal")
async def import_jep(body: JepImportRequest) -> ProposalDocument:
    merged = await offload(proposals.import_jep, body.proposal.to_domain(), body.jep, body.prospect_name)
    return ProposalDocument.from_domain(merged)


@router.post("/scope/library-items", response_model=ProposalDocument, summary="Add scope-library items")
async def add_library_items(body: AddLibraryItemsRequest) -> ProposalDocument:
    return ProposalDocument.from_domain(
        await offload(proposals.add_library_items, body.proposal.to_domain(), body.items, body.status)
    )


@router.post("/scope/library-addons", response_model=ProposalDocument, summary="Add add-on services (as Optional scope items)")
async def add_library_addons(body: AddLibraryAddonsRequest) -> ProposalDocument:
    return ProposalDocument.from_domain(await offload(proposals.add_library_addons, body.proposal.to_domain(), body.services))


@router.post("/scope/from-requirements", response_model=ProposalDocument, summary="Draft scope items for uncovered requirements")
async def draft_scope(body: ProposalRequest) -> ProposalDocument:
    return ProposalDocument.from_domain(await offload(proposals.draft_scope_from_requirements, body.proposal.to_domain()))


@router.post("/template", response_model=ProposalDocument, summary="Strip deal-specific content, keeping reusable boilerplate")
async def as_template(body: ProposalRequest) -> ProposalDocument:
    return ProposalDocument.from_domain(await offload(proposals.as_template, body.proposal.to_domain()))


@router.post("/pdf", response_class=Response, responses=binary_responses("pdf"), summary="Render the branded proposal / SOW PDF")
async def render_pdf(body: ProposalRequest) -> Response:
    content = await offload(proposals.render_pdf, body.proposal.to_domain())
    stem = f"{body.proposal.client.company or 'client'}_{body.proposal.document_type}"
    return file_response(content, stem=stem, ext="pdf")
