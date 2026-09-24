"""Module 4 — Executive Report (read-only, no API calls of its own).

Takes a pulled ``PortalSnapshot`` (Module 3) and, if available, the
``list[Finding]`` from an audit run (Module 2) — both already sitting in
``st.session_state`` by the time a user opens this page — and turns them
into a plain-language report: what the portal has, how it's structured, and
what's worth fixing.

Two audiences, two ``.docx`` exports:

- ``report_to_client_docx`` — polished, plain-language, capped examples.
  Meant to be handed to a client as-is.
- ``report_to_internal_docx`` — full technical detail: every finding, raw
  property groups, association type IDs. Meant for internal use/context,
  not client distribution.

Both exporters are built from the same ``ReportContext``, computed once by
``build_report_context`` so the two documents never disagree with each
other's numbers.
"""

from __future__ import annotations

import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from docx import Document

from core.audit import STANDARD_TYPE_ID_LABELS
from core.models import Finding, ObjectSchema, PortalPipeline, PortalSnapshot, SEVERITIES

# Common HubSpot engagement/activity object type IDs. Like
# STANDARD_TYPE_ID_LABELS, these are stable across every HubSpot portal —
# not specific to any one client — so it's safe to hardcode them here.
_ENGAGEMENT_TYPE_ID_LABELS: dict[str, str] = {
    "0-4": "Engagement",
    "0-18": "Communication",
    "0-27": "Task",
    "0-43": "Task Template",
    "0-46": "Note",
    "0-47": "Meeting",
    "0-48": "Call",
    "0-49": "Email",
    "0-51": "Conversation Session",
    "0-116": "Postal Mail",
}
_TYPE_ID_LABELS: dict[str, str] = {**STANDARD_TYPE_ID_LABELS, **_ENGAGEMENT_TYPE_ID_LABELS}

# HubSpot's own default property-group internal names have no separators
# (e.g. "contactinformation"), so a generic snake_case prettifier can't
# split them. These are HubSpot built-ins present on every portal, not
# client-specific, so it's a legitimate small reference table rather than
# an overfit hack.
_KNOWN_GROUP_LABELS: dict[str, str] = {
    "contactinformation": "Contact information",
    "companyinformation": "Company information",
    "dealinformation": "Deal information",
    "ticketinformation": "Ticket information",
    "socialmediainformation": "Social media",
    "analyticsinformation": "Analytics",
    "conversioninformation": "Conversion tracking",
    "emailinformation": "Email engagement",
    "smsinformation": "SMS",
    "contactlcs": "Lifecycle stage history",
    "companylcs": "Lifecycle stage history",
    "dealstages": "Deal stage history",
    "ticketstages": "Ticket stage history",
    "contactscripted": "Membership/scripted",
    "prospectingagent": "Prospecting agent",
    "targetaccountsinformation": "Target accounts",
    "objecttags": "Tags",
    "multiaccountmanagement": "Multi-account management",
}

CLIENT_EXAMPLES_PER_GROUP = 3

AREA_EXPLANATIONS: dict[str, dict[str, str]] = {
    "Properties": {
        "title": "Data fields",
        "what": "Duplicate or near-duplicate fields and dropdown options.",
        "impact": (
            "Teams can end up entering the same information in two different fields, or "
            "picking between two dropdown options that mean the same thing — splitting the "
            "data and skewing reports."
        ),
    },
    "Workflows": {
        "title": "Automation",
        "what": "Automations that update a record's data.",
        "impact": (
            "An automation that overwrites a field every time it runs — even if a person or "
            "another system already filled it in — can silently erase real data with no error "
            "or warning."
        ),
    },
    "Permissions": {
        "title": "Users & teams",
        "what": "Users not assigned to a team, and teams with nobody on them.",
        "impact": (
            "Unassigned users can fall through the cracks in team-based routing and "
            "reporting; empty teams are usually leftover clutter."
        ),
    },
    "Records": {
        "title": "Data completeness",
        "what": "Fields that should be filled in (per best practice) but are empty on a sample of records.",
        "impact": (
            "Missing data breaks segmentation, reporting, and any automation or integration "
            "that depends on that field being filled in."
        ),
    },
    "Associations": {
        "title": "Record relationships",
        "what": "Records missing an expected link to another object.",
        "impact": "A record with no expected connection is effectively invisible from the object it should roll up to.",
    },
    "Naming": {
        "title": "Naming consistency",
        "what": "Objects, properties, workflows, and pipelines that don't follow a consistent naming pattern.",
        "impact": "Inconsistent naming makes the system harder to search, hand off, and maintain — a housekeeping issue, not a data-risk one.",
    },
}

SEVERITY_META: dict[str, dict[str, str]] = {
    "High": {
        "label": "High priority",
        "tone": "These need attention soon — they can cause real data loss or broken processes.",
    },
    "Medium": {
        "label": "Medium priority",
        "tone": "Worth fixing, but not on fire — plan these into normal cleanup work.",
    },
    "Low": {
        "label": "Low priority / cleanup",
        "tone": "Cosmetic or minor data-hygiene items. Fix opportunistically.",
    },
}

_SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def prettify_group_name(raw: str) -> str:
    if not raw:
        return "Ungrouped"
    known = _KNOWN_GROUP_LABELS.get(raw.lower())
    if known:
        return known
    words = [w for w in raw.replace("-", "_").split("_") if w]
    if not words:
        return "Ungrouped"
    parts = ["HubSpot" if w.lower() == "hs" else w.lower() for w in words]
    parts[0] = parts[0].capitalize() if parts[0] != "HubSpot" else parts[0]
    return " ".join(parts)


@dataclass
class ObjectSummary:
    label: str
    object_type: str
    is_custom: bool
    property_count: int
    top_groups: list[tuple[str, int]] = field(default_factory=list)
    association_count: int = 0
    association_targets: list[str] = field(default_factory=list)


@dataclass
class PipelineSummary:
    object_type: str
    pipeline_count: int
    total_stage_count: int
    pipelines: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class FindingGroup:
    area: str
    severity: str
    count: int
    object_types: list[str] = field(default_factory=list)
    items: list[Finding] = field(default_factory=list)


@dataclass
class ReportContext:
    generated_at: str
    project_name: str
    snapshot: PortalSnapshot
    audited: bool

    standard_object_count: int
    custom_object_count: int
    total_properties: int
    object_summaries: list[ObjectSummary]
    pipeline_summaries: list[PipelineSummary]
    total_pipelines: int
    total_stages: int
    workflow_total: int
    workflow_enabled: int
    workflow_disabled: int
    workflow_unnamed: int
    team_total: int
    team_empty: int
    owner_total: int
    owner_unassigned: int
    owner_archived: int
    association_total: int

    finding_total: int
    severity_counts: dict[str, int]
    finding_groups: list[FindingGroup]
    rating: str
    rating_reason: str


# ---- computation ------------------------------------------------------------


def _summarize_object(schema: ObjectSchema, type_id_labels: dict[str, str], group_limit: int = 8) -> ObjectSummary:
    group_counts: Counter[str] = Counter(p.group_name or "ungrouped" for p in schema.properties)
    top_groups = [(prettify_group_name(name), count) for name, count in group_counts.most_common(group_limit)]
    association_targets = sorted({type_id_labels.get(a.to_object, a.to_object) for a in schema.associations})
    return ObjectSummary(
        label=schema.label,
        object_type=schema.object_type,
        is_custom=schema.is_custom,
        property_count=len(schema.properties),
        top_groups=top_groups,
        association_count=len(schema.associations),
        association_targets=association_targets,
    )


def _summarize_pipelines(pipelines: list[PortalPipeline]) -> list[PipelineSummary]:
    by_object: dict[str, list[PortalPipeline]] = defaultdict(list)
    for p in pipelines:
        by_object[p.object_type].append(p)
    summaries = [
        PipelineSummary(
            object_type=object_type,
            pipeline_count=len(pls),
            total_stage_count=sum(len(p.stages) for p in pls),
            pipelines=[(p.label, len(p.stages)) for p in pls],
        )
        for object_type, pls in by_object.items()
    ]
    summaries.sort(key=lambda s: -s.pipeline_count)
    return summaries


def _group_findings(findings: list[Finding]) -> list[FindingGroup]:
    buckets: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in findings:
        buckets[(f.area, f.severity)].append(f)
    groups = []
    for (area, severity), items in buckets.items():
        items_sorted = sorted(items, key=lambda f: (f.object_type, f.description))
        object_types = sorted({f.object_type for f in items if f.object_type})
        groups.append(FindingGroup(area=area, severity=severity, count=len(items), object_types=object_types, items=items_sorted))
    groups.sort(key=lambda g: (_SEVERITY_ORDER.get(g.severity, 3), -g.count, g.area))
    return groups


def _rate_portal_health(severity_counts: dict[str, int]) -> tuple[str, str]:
    high = severity_counts.get("High", 0)
    medium = severity_counts.get("Medium", 0)
    low = severity_counts.get("Low", 0)

    if high > 0:
        plural = "s" if high != 1 else ""
        return (
            "Needs Attention",
            f"{high} high-priority issue{plural} found — these can cause real data loss and should be addressed soon.",
        )
    if medium > 5:
        return "Fair", f"No high-priority issues, but {medium} medium-priority issues found — worth scheduling cleanup work."
    if medium > 0:
        plural = "s" if medium != 1 else ""
        return "Good", f"No high-priority issues; {medium} medium-priority item{plural} worth a look."
    if low > 0:
        plural = "s" if low != 1 else ""
        return "Excellent", f"No high- or medium-priority issues — only {low} low-priority cleanup item{plural} found."
    return "Excellent", "No issues found in this scan."


def build_report_context(
    snapshot: PortalSnapshot,
    findings: Optional[list[Finding]],
    project_name: str = "",
) -> ReportContext:
    audited = findings is not None
    findings = list(findings or [])

    type_id_labels = dict(_TYPE_ID_LABELS)
    type_id_labels.update({s.object_type: s.label for s in snapshot.object_schemas})

    object_summaries = [_summarize_object(s, type_id_labels) for s in snapshot.object_schemas]
    pipeline_summaries = _summarize_pipelines(snapshot.pipelines)

    standard_count = sum(1 for s in snapshot.object_schemas if not s.is_custom)
    custom_count = sum(1 for s in snapshot.object_schemas if s.is_custom)
    total_properties = sum(o.property_count for o in object_summaries)
    association_total = sum(o.association_count for o in object_summaries)

    workflow_total = len(snapshot.workflows)
    workflow_enabled = sum(1 for w in snapshot.workflows if w.enabled)
    workflow_unnamed = sum(1 for w in snapshot.workflows if w.name.strip().lower().startswith("unnamed workflow"))

    team_total = len(snapshot.teams)
    team_empty = sum(1 for t in snapshot.teams if t.member_count == 0)
    owner_total = len(snapshot.owners)
    owner_archived = sum(1 for o in snapshot.owners if o.archived)
    owner_unassigned = sum(1 for o in snapshot.owners if not o.teams and not o.archived)

    severity_counts = {sev: 0 for sev in SEVERITIES}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    finding_groups = _group_findings(findings)
    if audited:
        rating, rating_reason = _rate_portal_health(severity_counts)
    else:
        rating, rating_reason = (
            "Not Yet Audited",
            "Run the Portal Auditor first to get a health rating and a breakdown of issues found.",
        )

    return ReportContext(
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_name=project_name.strip() or "This HubSpot Portal",
        snapshot=snapshot,
        audited=audited,
        standard_object_count=standard_count,
        custom_object_count=custom_count,
        total_properties=total_properties,
        object_summaries=object_summaries,
        pipeline_summaries=pipeline_summaries,
        total_pipelines=len(snapshot.pipelines),
        total_stages=sum(len(p.stages) for p in snapshot.pipelines),
        workflow_total=workflow_total,
        workflow_enabled=workflow_enabled,
        workflow_disabled=workflow_total - workflow_enabled,
        workflow_unnamed=workflow_unnamed,
        team_total=team_total,
        team_empty=team_empty,
        owner_total=owner_total,
        owner_unassigned=owner_unassigned,
        owner_archived=owner_archived,
        association_total=association_total,
        finding_total=len(findings),
        severity_counts=severity_counts,
        finding_groups=finding_groups,
        rating=rating,
        rating_reason=rating_reason,
    )


# ---- shared presentation helpers --------------------------------------------


def _client_example_lines(group: FindingGroup) -> list[str]:
    shown = group.items[:CLIENT_EXAMPLES_PER_GROUP]
    lines = [f"{(f.object_type + ': ') if f.object_type else ''}{f.description}" for f in shown]
    remaining = group.count - len(shown)
    if remaining > 0:
        lines.append(f"...and {remaining} more like this.")
    return lines


def _top_recommendations(groups: list[FindingGroup], limit: int = 6) -> list[str]:
    ordered = [g for g in groups if g.severity in ("High", "Medium")] + [g for g in groups if g.severity == "Low"]
    seen: set[str] = set()
    steps: list[str] = []
    for g in ordered:
        fix = g.items[0].recommended_fix if g.items else ""
        if fix and fix not in seen:
            seen.add(fix)
            steps.append(fix)
        if len(steps) >= limit:
            break
    return steps


def _add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
    for row_values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row_values):
            cell.text = value


def _add_bullets(doc: Document, lines: list[str]) -> None:
    for line in lines:
        doc.add_paragraph(line, style="List Bullet")


# ---- client export (.docx) --------------------------------------------------


def report_to_client_docx(ctx: ReportContext) -> io.BytesIO:
    doc = Document()
    doc.add_heading(f"{ctx.project_name} — Portal Overview & Health Report", level=0)
    doc.add_paragraph(f"Generated {ctx.generated_at}")
    doc.add_paragraph(
        "This report explains, in plain language, what your HubSpot portal currently has set "
        "up, how the different pieces connect, and what's worth fixing. It's based on an "
        "automated, read-only scan of your portal — nothing was changed to produce it."
    )

    doc.add_heading("Overall health", level=1)
    rating_p = doc.add_paragraph()
    rating_p.add_run(f"Rating: {ctx.rating}").bold = True
    doc.add_paragraph(ctx.rating_reason)
    if ctx.audited:
        _add_table(
            doc,
            ["Priority", "Count"],
            [[SEVERITY_META[sev]["label"], str(ctx.severity_counts.get(sev, 0))] for sev in SEVERITIES],
        )
        doc.add_paragraph(
            "This rating is based on high- and medium-priority findings only. Low-priority "
            "items are cosmetic/data-hygiene cleanup and don't change the rating."
        )

    doc.add_heading("What's in your portal", level=1)
    doc.add_paragraph(
        f"Your portal has {ctx.standard_object_count} standard object type(s) (like Contacts, "
        f"Companies, Deals) and {ctx.custom_object_count} custom object type(s) built "
        f"specifically for this implementation, holding {ctx.total_properties} data fields in "
        "total."
    )
    _add_table(
        doc,
        ["Object", "Kind", "Data fields", "Connects to"],
        [
            [
                obj.label,
                "Custom" if obj.is_custom else "Standard",
                str(obj.property_count),
                ", ".join(obj.association_targets) if obj.association_targets else "—",
            ]
            for obj in ctx.object_summaries
        ],
    )

    if ctx.pipeline_summaries:
        doc.add_heading("Sales & service pipelines", level=1)
        doc.add_paragraph(
            f"{ctx.total_pipelines} pipeline(s) across {len(ctx.pipeline_summaries)} object "
            f"type(s), with {ctx.total_stages} stages in total."
        )
        _add_bullets(
            doc,
            [f"{ps.object_type}: {ps.pipeline_count} pipeline(s), {ps.total_stage_count} stages total." for ps in ctx.pipeline_summaries],
        )

    doc.add_heading("Automation", level=1)
    doc.add_paragraph(
        f"{ctx.workflow_total} workflow(s) exist, {ctx.workflow_enabled} currently enabled and "
        f"{ctx.workflow_disabled} turned off."
    )
    if ctx.workflow_unnamed:
        doc.add_paragraph(
            f"{ctx.workflow_unnamed} of these still have HubSpot's generic default name "
            "('Unnamed workflow - <date>'), which usually means they were created by an "
            "integration or API call and never labeled — worth naming for anyone auditing or "
            "handing off the portal later."
        )

    doc.add_heading("Users & teams", level=1)
    doc.add_paragraph(
        f"{ctx.owner_total} user(s) and {ctx.team_total} team(s) are set up. "
        f"{ctx.owner_unassigned} active user(s) aren't on any team, and {ctx.team_empty} "
        "team(s) have no members — usually safe to clean up, but worth a quick confirm."
    )

    doc.add_heading("Things worth fixing", level=1)
    if not ctx.audited:
        doc.add_paragraph("Run the Portal Auditor first to populate this section.")
    elif not ctx.finding_groups:
        doc.add_paragraph("No issues found in this scan.")
    else:
        for sev in SEVERITIES:
            sev_groups = [g for g in ctx.finding_groups if g.severity == sev]
            if not sev_groups:
                continue
            doc.add_heading(f"{SEVERITY_META[sev]['label']} ({sum(g.count for g in sev_groups)})", level=2)
            doc.add_paragraph(SEVERITY_META[sev]["tone"])
            for group in sev_groups:
                meta = AREA_EXPLANATIONS.get(group.area, {})
                p = doc.add_paragraph()
                p.add_run(f"{meta.get('title', group.area)} ({group.count})").bold = True
                if meta.get("impact"):
                    doc.add_paragraph(meta["impact"])
                _add_bullets(doc, _client_example_lines(group))

    doc.add_heading("Recommended next steps", level=1)
    if ctx.audited:
        steps = _top_recommendations(ctx.finding_groups)
        if steps:
            for i, step in enumerate(steps, start=1):
                doc.add_paragraph(f"{i}. {step}")
        else:
            doc.add_paragraph("Nothing urgent — see the cleanup items above when convenient.")
    else:
        doc.add_paragraph("Run the Portal Auditor to get prioritized recommendations here.")

    doc.add_heading("How this report was built", level=1)
    doc.add_paragraph(
        "Generated automatically from a read-only scan of your HubSpot portal's schemas, "
        "properties, pipelines, workflows, teams, and owners, plus a sample of records for "
        "data-completeness checks. No data in your portal was changed to produce this report."
    )

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ---- internal export (.docx) -------------------------------------------------


def report_to_internal_docx(ctx: ReportContext) -> io.BytesIO:
    doc = Document()
    doc.add_heading(f"Internal Report — {ctx.project_name}", level=0)
    doc.add_paragraph(f"Generated {ctx.generated_at}")
    p = doc.add_paragraph()
    p.add_run("Internal use/context only — not for client distribution.").italic = True

    doc.add_heading("Health rating", level=1)
    rating_p = doc.add_paragraph()
    rating_p.add_run(f"{ctx.rating}").bold = True
    rating_p.add_run(f" — {ctx.rating_reason}")
    if ctx.audited:
        _add_table(
            doc,
            ["Priority", "Count"],
            [[sev, str(ctx.severity_counts.get(sev, 0))] for sev in SEVERITIES],
        )

    doc.add_heading("Portal stats", level=1)
    _add_bullets(
        doc,
        [
            f"Standard objects: {ctx.standard_object_count}",
            f"Custom objects: {ctx.custom_object_count}",
            f"Total properties: {ctx.total_properties}",
            f"Total associations declared (custom object schemas): {ctx.association_total}",
            f"Pipelines: {ctx.total_pipelines} ({ctx.total_stages} stages total)",
            (
                f"Workflows: {ctx.workflow_total} ({ctx.workflow_enabled} enabled, "
                f"{ctx.workflow_disabled} disabled, {ctx.workflow_unnamed} still named 'Unnamed workflow ...')"
            ),
            f"Teams: {ctx.team_total} ({ctx.team_empty} with zero members)",
            f"Owners: {ctx.owner_total} ({ctx.owner_unassigned} unassigned to a team, {ctx.owner_archived} archived)",
        ],
    )

    doc.add_heading("Object model", level=1)
    _add_table(
        doc,
        ["Object", "Kind", "object_type", "Properties", "Top property groups", "Associations", "Connects to"],
        [
            [
                obj.label,
                "Custom" if obj.is_custom else "Standard",
                obj.object_type,
                str(obj.property_count),
                ", ".join(f"{name} ({count})" for name, count in obj.top_groups),
                str(obj.association_count),
                ", ".join(obj.association_targets),
            ]
            for obj in ctx.object_summaries
        ],
    )

    if ctx.pipeline_summaries:
        doc.add_heading("Pipelines", level=1)
        _add_table(
            doc,
            ["Object", "Pipelines", "Total stages", "Detail"],
            [
                [
                    ps.object_type,
                    str(ps.pipeline_count),
                    str(ps.total_stage_count),
                    "; ".join(f"{label} ({count} stages)" for label, count in ps.pipelines),
                ]
                for ps in ctx.pipeline_summaries
            ],
        )

    doc.add_heading("Findings — full detail", level=1)
    if not ctx.audited:
        doc.add_paragraph("No audit has been run yet. Run the Portal Auditor to populate this section.")
    elif not ctx.finding_groups:
        doc.add_paragraph("No findings — the last audit run found no issues.")
    else:
        areas = sorted({g.area for g in ctx.finding_groups})

        doc.add_heading("Summary by area and priority", level=2)
        summary_rows = []
        for area in areas:
            counts = {sev: 0 for sev in SEVERITIES}
            for g in ctx.finding_groups:
                if g.area == area:
                    counts[g.severity] = g.count
            summary_rows.append([area, str(counts["High"]), str(counts["Medium"]), str(counts["Low"]), str(sum(counts.values()))])
        _add_table(doc, ["Area", "High", "Medium", "Low", "Total"], summary_rows)

        for area in areas:
            meta = AREA_EXPLANATIONS.get(area, {})
            doc.add_heading(meta.get("title", area), level=2)
            if meta.get("what"):
                note_p = doc.add_paragraph()
                note_p.add_run(f"{meta['what']} {meta.get('impact', '')}").italic = True
            rows = [
                [f.severity, f.object_type, f.description, f.recommended_fix]
                for g in ctx.finding_groups
                if g.area == area
                for f in g.items
            ]
            _add_table(doc, ["Priority", "Object", "Description", "Recommended Fix"], rows)

    doc.add_heading("Methodology notes", level=1)
    _add_bullets(
        doc,
        [
            "Read-only scan: nothing in the portal was created, updated, or deleted.",
            (
                "Record-level checks (unused/required properties, orphaned records) sample "
                "records rather than pulling every record — sample size is noted in each finding."
            ),
            "Health rating is derived from High/Medium finding counts only; Low-priority items are excluded from the rating.",
        ],
    )

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
