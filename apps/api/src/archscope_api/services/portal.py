"""Live-portal use cases (Modules 2, 2B, 3, 4): pull a snapshot, audit it,
rate its properties, and turn it into an executive report. Portal access
is always through the read-only :class:`PortalReader` port."""

from __future__ import annotations

from dataclasses import dataclass

from archscope_domain import diagram as dd
from archscope_domain.audit import PortalAuditor
from archscope_domain.docgen import DocumentationGenerator, snapshot_to_docx, snapshot_to_markdown
from archscope_domain.models import SEVERITIES, Finding, PortalSnapshot
from archscope_domain.ports import PortalReader
from archscope_domain.property_audit import (
    PropertyAuditResult,
    property_audit_to_pdf,
    property_audit_to_xlsx,
    run_property_audit,
)
from archscope_domain.report import ReportContext, build_report_context, report_to_client_docx, report_to_internal_docx

from .architecture import rules_engine


@dataclass(frozen=True)
class AuditOutcome:
    findings: list[Finding]
    by_severity: dict[str, int]
    by_area: dict[str, int]


def pull_snapshot(reader: PortalReader) -> PortalSnapshot:
    return DocumentationGenerator(reader).build_snapshot()


def snapshot_markdown(snapshot: PortalSnapshot) -> str:
    return snapshot_to_markdown(snapshot)


def snapshot_docx(snapshot: PortalSnapshot) -> bytes:
    return snapshot_to_docx(snapshot).getvalue()


def audit(reader: PortalReader, snapshot: PortalSnapshot) -> AuditOutcome:
    findings = PortalAuditor(reader, rules_engine()).run(snapshot)
    by_severity = {severity: 0 for severity in SEVERITIES} | dd.findings_by_severity(findings)
    return AuditOutcome(findings=findings, by_severity=by_severity, by_area=dd.findings_by_area(findings))


def property_audit(reader: PortalReader, snapshot: PortalSnapshot) -> PropertyAuditResult:
    return run_property_audit(reader, snapshot, rules_engine())


def property_audit_xlsx(result: PropertyAuditResult, project_name: str) -> bytes:
    return property_audit_to_xlsx(result, project_name)


def property_audit_pdf(result: PropertyAuditResult, project_name: str) -> bytes:
    return property_audit_to_pdf(result, project_name)


def report_context(snapshot: PortalSnapshot, findings: list[Finding] | None, project_name: str) -> ReportContext:
    return build_report_context(snapshot, findings, project_name=project_name)


def report_docx(ctx: ReportContext, audience: str) -> bytes:
    render = report_to_client_docx if audience == "client" else report_to_internal_docx
    return render(ctx).getvalue()
