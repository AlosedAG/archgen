"""Proposal & SOW Builder (Module 10). The proposal itself is saved as the
project's module state; these endpoints compute on it, render it, and
manage the workspace's shared templates."""

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
    ProposalTemplateSave,
    ProposalTemplateSummary,
    ProposalTemplateUpdate,
    ScopeRow,
    WrdImportRequest,
)
from ...services import proposal_templates, proposals
from ...services.auth import Principal
from ..deps import DbDep, PrincipalDep, binary_responses, file_response, offload

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


# ---- Shared templates -----------------------------------------------------------------------------


def _template(s: proposal_templates.TemplateSummary, principal: Principal) -> ProposalTemplateSummary:
    t = s.template
    data = t.data or {}
    return ProposalTemplateSummary(
        id=t.id,
        name=t.name,
        description=t.description,
        created_by=s.created_by_name,
        updated_at=t.updated_at,
        requirement_count=sum(1 for r in data.get("requirements", []) if str(r.get("Requirement", "")).strip()),
        scope_count=sum(1 for r in data.get("scope", []) if str(r.get("Item", "")).strip()),
        can_delete=proposal_templates.can_delete(principal, t),
    )


@router.get("/templates", response_model=list[ProposalTemplateSummary], summary="The workspace's saved proposal templates")
def list_templates(principal: PrincipalDep, db: DbDep) -> list[ProposalTemplateSummary]:
    return [_template(s, principal) for s in proposal_templates.list_templates(db, principal)]


@router.post(
    "/templates", response_model=ProposalTemplateSummary, status_code=201, summary="Save a proposal as a shared template"
)
def save_template(body: ProposalTemplateSave, principal: PrincipalDep, db: DbDep) -> ProposalTemplateSummary:
    template = proposal_templates.save_template(
        db, principal, name=body.name, description=body.description, proposal=body.proposal.to_domain(), replace=body.replace
    )
    return _template(proposal_templates.summary(db, template), principal)


@router.patch("/templates/{template_id}", response_model=ProposalTemplateSummary, summary="Rename or re-describe a template")
def update_template(
    template_id: str, body: ProposalTemplateUpdate, principal: PrincipalDep, db: DbDep
) -> ProposalTemplateSummary:
    template = proposal_templates.rename_template(db, principal, template_id, name=body.name, description=body.description)
    return _template(proposal_templates.summary(db, template), principal)


@router.delete("/templates/{template_id}", status_code=204, summary="Delete a template (its creator or an admin)")
def delete_template(template_id: str, principal: PrincipalDep, db: DbDep) -> Response:
    proposal_templates.delete_template(db, principal, template_id)
    return Response(status_code=204)


@router.post(
    "/templates/{template_id}/apply", response_model=ProposalDocument, summary="Start the given proposal from a template"
)
def apply_template(template_id: str, body: ProposalRequest, principal: PrincipalDep, db: DbDep) -> ProposalDocument:
    """The template's content, keeping this proposal's client details, dates and reference."""
    return ProposalDocument.from_domain(proposal_templates.apply_template(db, principal, template_id, body.proposal.to_domain()))
