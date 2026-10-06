"""Live-portal modules: Documentation Generator (3), Portal Auditor (2),
Property Audit (2B), Executive Report (4). Read-only against HubSpot."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response
from fastapi.responses import PlainTextResponse

from ...schemas.audit import (
    AuditRequest,
    AuditResult,
    PropertyAuditExportRequest,
    PropertyAuditRequest,
    PropertyAuditResult,
)
from ...schemas.portal import PortalSnapshot, findings_from_domain, findings_to_domain
from ...schemas.report import ReportContext, ReportRequest
from ...services import portal
from ..deps import PortalReaderDep, binary_responses, file_response, offload

router = APIRouter(tags=["portal"])


@router.post("/portal/snapshot", response_model=PortalSnapshot, summary="Pull a read-only snapshot of a HubSpot portal")
async def pull_snapshot(reader: PortalReaderDep) -> PortalSnapshot:
    """Schemas, properties, pipelines, workflows, owners and teams. A
    missing scope degrades to a ``warnings`` entry instead of failing."""
    snapshot = await offload(portal.pull_snapshot, reader)
    return PortalSnapshot.from_domain(snapshot)


@router.post(
    "/portal/snapshot/document",
    response_class=Response,
    responses=binary_responses("docx", "md"),
    summary="Render portal documentation (Markdown or Word)",
)
async def snapshot_document(body: PortalSnapshot, format: Literal["md", "docx"] = Query("docx")) -> Response:
    snapshot = body.to_domain()
    if format == "md":
        return PlainTextResponse(await offload(portal.snapshot_markdown, snapshot), media_type="text/markdown; charset=utf-8")
    return file_response(await offload(portal.snapshot_docx, snapshot), stem="portal_documentation", ext="docx")


@router.post("/audits", response_model=AuditResult, summary="Audit a snapshot against best-practice rules")
async def run_audit(body: AuditRequest, reader: PortalReaderDep) -> AuditResult:
    """Structural checks run on the snapshot; record-level checks (fill
    rates, orphaned records) sample the live portal, read-only."""
    outcome = await offload(portal.audit, reader, body.snapshot.to_domain())
    return AuditResult(findings=findings_from_domain(outcome.findings), by_severity=outcome.by_severity, by_area=outcome.by_area)


@router.post("/property-audits", response_model=PropertyAuditResult, summary="Rate every property Keep / Review / Remove")
async def run_property_audit(body: PropertyAuditRequest, reader: PortalReaderDep) -> PropertyAuditResult:
    result = await offload(portal.property_audit, reader, body.snapshot.to_domain())
    return PropertyAuditResult.from_domain(result)


@router.post(
    "/property-audits/export",
    response_class=Response,
    responses=binary_responses("xlsx", "pdf"),
    summary="Export a property audit (Excel workbook or PDF report)",
)
async def export_property_audit(body: PropertyAuditExportRequest, format: Literal["xlsx", "pdf"] = Query("xlsx")) -> Response:
    result = body.result.to_domain()
    render = portal.property_audit_xlsx if format == "xlsx" else portal.property_audit_pdf
    content = await offload(render, result, body.project_name)
    return file_response(content, stem=f"{body.project_name or 'portal'}_property_audit", ext=format)


@router.post("/reports/context", response_model=ReportContext, summary="Compute executive-report figures")
async def report_context(body: ReportRequest) -> ReportContext:
    ctx = await offload(portal.report_context, body.snapshot.to_domain(), findings_to_domain(body.findings), body.project_name)
    return ReportContext.from_domain(ctx)


@router.post(
    "/reports/document",
    response_class=Response,
    responses=binary_responses("docx"),
    summary="Render the executive report (client or internal edition)",
)
async def report_document(body: ReportRequest, audience: Literal["client", "internal"] = Query("client")) -> Response:
    ctx = await offload(portal.report_context, body.snapshot.to_domain(), findings_to_domain(body.findings), body.project_name)
    content = await offload(portal.report_docx, ctx, audience)
    return file_response(content, stem=f"{body.project_name or 'portal'}_{audience}_report", ext="docx")
