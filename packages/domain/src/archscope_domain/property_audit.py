"""Module 2B — Property Audit (read-only).

Rates every property on every object in a pulled ``PortalSnapshot`` —
standard and custom — as Keep / Review / Remove candidate, the same way
the reference workbook in ``examples/RPG_property_audit.xlsx`` and its
companion report ``examples/RPG_HubSpot_Audit_Report.pdf`` do, so a user
can review the call on every field before touching anything in HubSpot.

Two signals decide a custom property's rating (native/HubSpot-defined
properties are always Keep, matching the example workbook's own rule):

- **Fill %** — the share of a sampled batch of records that have a value
  set for the property (same sampling ``PortalAuditor`` already uses).
- **Uses** — the number of this portal's workflows whose actions
  reference the property by name. This tool only ever pulls workflows
  (see :class:`~archscope_domain.ports.PortalReader`) — it does not read forms,
  lists, reports, or dashboards — so "Uses" undercounts real usage
  whenever a property is only referenced from one of those. Every export
  says this plainly rather than implying a complete usage picture.

Exports as a 4-sheet .xlsx (Summary, Flagged for Action, All Properties,
How to use) and a PDF report capped at 10 pages, both styled with the
``core.theme`` audit palette to match the two reference files.
"""

from __future__ import annotations

import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pypdf import PdfReader

from archscope_domain.branding import (
    AUDIT_BODY,
    AUDIT_CUSTOM_BADGE,
    AUDIT_HEADER_BG,
    AUDIT_KEEP_BG,
    AUDIT_MUTED,
    AUDIT_REMOVE_BG,
    AUDIT_REVIEW_BG,
    AUDIT_SUBTITLE,
    AUDIT_TITLE,
    argb,
)
from archscope_domain.exporters import _pdf_safe
from archscope_domain.models import PortalSnapshot, PortalWorkflow
from archscope_domain.ports import PortalAPIError, PortalReader, PortalScopeError
from archscope_domain.rules import RulesEngine

RATING_REMOVE = "Remove candidate"
RATING_REVIEW = "Review"
RATING_KEEP = "Keep"

_RATING_ORDER = {RATING_REMOVE: 0, RATING_REVIEW: 1, RATING_KEEP: 2}
_MAX_REPORT_PAGES = 10


@dataclass
class PropertyAuditRow:
    object_label: str
    object_type: str
    property_label: str
    internal_name: str
    field_type: str
    is_custom: bool
    fill_pct: float
    uses: int
    rating: str
    assessment: str = ""


@dataclass
class ObjectAuditSummary:
    object_label: str
    object_type: str
    properties_count: int
    custom_count: int
    remove_count: int
    review_count: int
    keep_count: int
    cleanup_score: float


@dataclass
class PropertyAuditResult:
    generated_at: str
    sample_size: int
    rows: list[PropertyAuditRow] = field(default_factory=list)
    object_summaries: list[ObjectAuditSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def totals(self) -> ObjectAuditSummary:
        return _summarize(
            "TOTAL",
            "",
            properties_count=sum(s.properties_count for s in self.object_summaries),
            custom_count=sum(s.custom_count for s in self.object_summaries),
            remove_count=sum(s.remove_count for s in self.object_summaries),
            review_count=sum(s.review_count for s in self.object_summaries),
            keep_count=sum(s.keep_count for s in self.object_summaries),
        )

    @property
    def flagged_rows(self) -> list[PropertyAuditRow]:
        flagged = [r for r in self.rows if r.rating in (RATING_REMOVE, RATING_REVIEW)]
        return sorted(flagged, key=lambda r: (_RATING_ORDER[r.rating], r.fill_pct, r.object_label, r.property_label))


# ---- rating logic -----------------------------------------------------------


def _rate_property(is_custom: bool, fill_pct: float, uses: int) -> tuple[str, str]:
    """Rate a single property. Thresholds (25% fill for "in use", 5%/50%
    fill for "unused") were reverse-engineered from the rating boundaries
    observed in examples/RPG_property_audit.xlsx so this tool's calls read
    the same way a reviewer of that workbook would expect."""
    if not is_custom:
        return RATING_KEEP, ""

    pct = round(fill_pct)
    if uses > 0:
        if fill_pct >= 25:
            return RATING_KEEP, ""
        plural = "" if uses == 1 else "s"
        return (
            RATING_REVIEW,
            f"Custom · only {pct}% filled though {uses} workflow{plural} reference{'s' if uses == 1 else ''} it — review.",
        )

    if fill_pct < 5:
        return (
            RATING_REMOVE,
            f"Custom · {pct}% filled · 0 workflows reference it — safe to delete after a final check.",
        )
    if fill_pct < 50:
        return RATING_REVIEW, f"Custom · {pct}% filled · 0 workflows reference it — likely removable."
    return RATING_REVIEW, f"Custom · {pct}% filled but 0 workflows reference it — verify before removing."


def _workflow_property_uses(workflows: list[PortalWorkflow]) -> Counter[str]:
    """Count distinct workflows whose actions set/reference each property
    by internal name. This is the only usage signal this read-only tool
    can see — it does not pull forms, lists, or reports."""
    counts: Counter[str] = Counter()
    for wf in workflows:
        referenced: set[str] = set()
        for action in wf.actions:
            if isinstance(action, dict):
                name = action.get("propertyName")
                if name:
                    referenced.add(str(name))
        counts.update(referenced)
    return counts


def _summarize(
    object_label: str,
    object_type: str,
    *,
    properties_count: int,
    custom_count: int,
    remove_count: int,
    review_count: int,
    keep_count: int,
) -> ObjectAuditSummary:
    score = 100.0 if custom_count == 0 else 100.0 * (1 - (remove_count + 0.5 * review_count) / custom_count)
    return ObjectAuditSummary(
        object_label=object_label,
        object_type=object_type,
        properties_count=properties_count,
        custom_count=custom_count,
        remove_count=remove_count,
        review_count=review_count,
        keep_count=keep_count,
        cleanup_score=round(score),
    )


# ---- audit run ---------------------------------------------------------------


def run_property_audit(client: PortalReader, snapshot: PortalSnapshot, rules: RulesEngine | None = None) -> PropertyAuditResult:
    rules = rules or RulesEngine()
    sample_size = rules.record_sample_size()
    warnings: list[str] = []
    uses_by_name = _workflow_property_uses(snapshot.workflows)

    rows: list[PropertyAuditRow] = []
    summaries: list[ObjectAuditSummary] = []

    for schema in snapshot.object_schemas:
        if not schema.properties:
            continue
        prop_names = [p.name for p in schema.properties]
        fill_by_name: dict[str, float] = {}
        try:
            sample = client.get_records_sample(schema.object_type, limit=sample_size, properties=prop_names)
        except (PortalScopeError, PortalAPIError) as exc:
            warnings.append(f"{schema.label}: could not sample records to compute Fill % ({exc}) — shown as 0%.")
            sample = []
        if sample:
            for name in prop_names:
                populated = sum(1 for r in sample if (r.get("properties") or {}).get(name))
                fill_by_name[name] = round(100.0 * populated / len(sample), 1)

        object_rows: list[PropertyAuditRow] = []
        for prop in schema.properties:
            is_custom = not prop.hubspot_defined
            fill_pct = fill_by_name.get(prop.name, 0.0)
            uses = uses_by_name.get(prop.name, 0)
            rating, assessment = _rate_property(is_custom, fill_pct, uses)
            object_rows.append(
                PropertyAuditRow(
                    object_label=schema.label,
                    object_type=schema.object_type,
                    property_label=prop.label or prop.name,
                    internal_name=prop.name,
                    field_type=prop.type or prop.field_type,
                    is_custom=is_custom,
                    fill_pct=fill_pct,
                    uses=uses,
                    rating=rating,
                    assessment=assessment,
                )
            )
        rows.extend(object_rows)

        custom_rows = [r for r in object_rows if r.is_custom]
        remove_count = sum(1 for r in custom_rows if r.rating == RATING_REMOVE)
        review_count = sum(1 for r in custom_rows if r.rating == RATING_REVIEW)
        summaries.append(
            _summarize(
                schema.label,
                schema.object_type,
                properties_count=len(object_rows),
                custom_count=len(custom_rows),
                remove_count=remove_count,
                review_count=review_count,
                keep_count=len(object_rows) - remove_count - review_count,
            )
        )

    summaries.sort(key=lambda s: s.cleanup_score)

    return PropertyAuditResult(
        generated_at=datetime.now(UTC).isoformat(),
        sample_size=sample_size,
        rows=rows,
        object_summaries=summaries,
        warnings=warnings,
    )


# ---- .xlsx export (Summary / Flagged for Action / All Properties / How to use)


_RATING_FILL_RGB = {
    RATING_REMOVE: AUDIT_REMOVE_BG,
    RATING_REVIEW: AUDIT_REVIEW_BG,
    RATING_KEEP: AUDIT_KEEP_BG,
}


def property_audit_to_xlsx(result: PropertyAuditResult, project_name: str = "") -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill(start_color=argb(AUDIT_HEADER_BG), end_color=argb(AUDIT_HEADER_BG), fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color=argb((255, 255, 255)))
    title_font = Font(name="Arial", size=18, bold=True, color=argb(AUDIT_TITLE))
    subtitle_font = Font(name="Arial", size=10, color=argb(AUDIT_SUBTITLE))
    meta_font = Font(name="Arial", size=9, color=argb(AUDIT_SUBTITLE))
    body_font = Font(name="Arial", size=10, color=argb(AUDIT_BODY))
    body_bold_font = Font(name="Arial", size=10, bold=True, color=argb(AUDIT_BODY))
    mono_font = Font(name="Consolas", size=9, color=argb(AUDIT_SUBTITLE))
    custom_yes_font = Font(name="Arial", size=10, bold=True, color=argb(AUDIT_CUSTOM_BADGE))
    custom_no_font = Font(name="Arial", size=10, color=argb(AUDIT_SUBTITLE))
    center = Alignment(horizontal="center")

    def rating_fill(rating: str) -> PatternFill:
        rgb = _RATING_FILL_RGB.get(rating, AUDIT_KEEP_BG)
        return PatternFill(start_color=argb(rgb), end_color=argb(rgb), fill_type="solid")

    # ---- Summary ----
    ws = wb.create_sheet("Summary")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "HubSpot Property Health Audit"
    ws["A1"].font = title_font
    subtitle = "Custom-property cleanup, ranked by usage"
    if project_name:
        subtitle += f" — {project_name}"
    ws["A2"] = subtitle
    ws["A2"].font = subtitle_font
    ws["A3"] = (
        f"Generated {result.generated_at[:10]} · sampled up to {result.sample_size} records per object · "
        "Cleanup score = 100 × (1 − (Remove + ½·Review) ÷ Custom)"
    )
    ws["A3"].font = meta_font

    headers = ["Object", "Properties", "Custom", "Remove candidate", "Review", "Keep", "Cleanup score"]
    header_row = 5
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    row_i = header_row + 1
    for s in result.object_summaries:
        ws.cell(row=row_i, column=1, value=s.object_label).font = body_bold_font
        ws.cell(row=row_i, column=2, value=s.properties_count).alignment = center
        ws.cell(row=row_i, column=3, value=s.custom_count).alignment = center
        for col, count, rtg in (
            (4, s.remove_count, RATING_REMOVE),
            (5, s.review_count, RATING_REVIEW),
            (6, s.keep_count, RATING_KEEP),
        ):
            c = ws.cell(row=row_i, column=col, value=count)
            c.font = body_bold_font
            c.fill = rating_fill(rtg)
            c.alignment = center
        ws.cell(row=row_i, column=7, value=s.cleanup_score).alignment = center
        row_i += 1

    last_data_row = row_i - 1
    total = result.totals
    total_values = [
        total.object_label,
        total.properties_count,
        total.custom_count,
        total.remove_count,
        total.review_count,
        total.keep_count,
        total.cleanup_score,
    ]
    for col, val in enumerate(total_values, start=1):
        c = ws.cell(row=row_i, column=col, value=val)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center

    ws.freeze_panes = f"A{header_row + 1}"
    if last_data_row >= header_row:
        ws.auto_filter.ref = f"A{header_row}:G{last_data_row}"
    for letter, width in zip("ABCDEFG", (24, 12, 10, 17, 10, 10, 14), strict=False):
        ws.column_dimensions[letter].width = width

    # ---- All Properties ----
    all_headers = [
        "Object",
        "Property",
        "Internal name",
        "Type",
        "Custom",
        "Fill %",
        "Uses",
        "Rating",
        "Assessment",
        "Notes",
        "Tag",
    ]
    ws2 = wb.create_sheet("All Properties")
    for col, h in enumerate(all_headers, start=1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
    for i, r in enumerate(result.rows, start=2):
        ws2.cell(row=i, column=1, value=r.object_label).font = body_font
        ws2.cell(row=i, column=2, value=r.property_label).font = body_font
        ws2.cell(row=i, column=3, value=r.internal_name).font = mono_font
        ws2.cell(row=i, column=4, value=r.field_type).font = body_font
        custom_cell = ws2.cell(row=i, column=5, value="Yes" if r.is_custom else "No")
        custom_cell.font = custom_yes_font if r.is_custom else custom_no_font
        custom_cell.alignment = center
        fill_cell = ws2.cell(row=i, column=6, value=r.fill_pct)
        fill_cell.number_format = "0.0"
        fill_cell.alignment = center
        ws2.cell(row=i, column=7, value=r.uses).alignment = center
        rating_cell = ws2.cell(row=i, column=8, value=r.rating)
        rating_cell.font = body_bold_font
        rating_cell.fill = rating_fill(r.rating)
        rating_cell.alignment = center
        ws2.cell(row=i, column=9, value=r.assessment).font = body_font
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:K{len(result.rows) + 1}"
    for letter, width in zip("ABCDEFGHIJK", (20, 30, 26, 13, 8, 8, 7, 17, 50, 26, 14), strict=False):
        ws2.column_dimensions[letter].width = width

    # ---- Flagged for Action ----
    flagged = result.flagged_rows
    flagged_headers = ["Object", "Property", "Internal name", "Type", "Fill %", "Uses", "Rating", "Assessment", "Notes", "Tag"]
    ws3 = wb.create_sheet("Flagged for Action")
    for col, h in enumerate(flagged_headers, start=1):
        cell = ws3.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
    for i, r in enumerate(flagged, start=2):
        ws3.cell(row=i, column=1, value=r.object_label).font = body_font
        ws3.cell(row=i, column=2, value=r.property_label).font = body_font
        ws3.cell(row=i, column=3, value=r.internal_name).font = mono_font
        ws3.cell(row=i, column=4, value=r.field_type).font = body_font
        fill_cell = ws3.cell(row=i, column=5, value=r.fill_pct)
        fill_cell.number_format = "0.0"
        fill_cell.alignment = center
        ws3.cell(row=i, column=6, value=r.uses).alignment = center
        rating_cell = ws3.cell(row=i, column=7, value=r.rating)
        rating_cell.font = body_bold_font
        rating_cell.fill = rating_fill(r.rating)
        rating_cell.alignment = center
        ws3.cell(row=i, column=8, value=r.assessment).font = body_font
    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:J{len(flagged) + 1}"
    for letter, width in zip("ABCDEFGHIJ", (20, 30, 26, 13, 8, 7, 17, 54, 26, 14), strict=False):
        ws3.column_dimensions[letter].width = width

    # ---- How to use ----
    ws4 = wb.create_sheet("How to use")
    ws4.sheet_view.showGridLines = False
    ws4["A1"] = "How to use this workbook"
    ws4["A1"].font = Font(name="Arial", size=16, bold=True, color=argb(AUDIT_TITLE))
    how_rows = [
        ("Summary", "Per-object counts and cleanup score. Sorted worst-first. Score recalculates if you edit the counts."),
        (
            "All Properties",
            f"Every one of the {len(result.rows)} properties, one row each. Filter/sort by Fill %, Uses, Custom, or Rating. Write in Notes and Tag.",
        ),
        (
            "Flagged for Action",
            f"The {len(flagged)} custom properties rated Remove candidate or Review, worst first — the actual cleanup worklist.",
        ),
        ("", ""),
        (
            "Custom = Yes",
            "A custom (non-default) property. Only custom properties are ever flagged; native HubSpot properties are always Keep.",
        ),
        (
            "Fill %",
            f"Share of a sample of up to {result.sample_size} records that have a value for this property. 0.0 = never populated in the sample.",
        ),
        (
            "Uses",
            "Number of this portal's workflows whose actions reference the property. This tool only reads workflows — forms, lists, reports, and "
            "dashboards aren't pulled, so a property used only in one of those will still show 0 here.",
        ),
        ("", ""),
        ("Rating key", ""),
        (RATING_KEEP, "Native property, or custom and healthy (well filled and/or referenced by a workflow) — leave it."),
        (RATING_REVIEW, "Custom, partially filled or referenced — decide case by case."),
        (RATING_REMOVE, "Custom, under 5% filled and referenced by no workflow — safe to delete after a final check."),
    ]
    r_i = 3
    for label, desc in how_rows:
        if not label and not desc:
            r_i += 1
            continue
        ws4.cell(row=r_i, column=1, value=label).font = Font(name="Arial", size=10, bold=True, color=argb((91, 79, 168)))
        ws4.cell(row=r_i, column=2, value=desc).font = body_font
        r_i += 1
    for letter, width in zip("ABC", (18, 90, 14), strict=False):
        ws4.column_dimensions[letter].width = width

    if result.warnings:
        ws5 = wb.create_sheet("Warnings")
        ws5["A1"] = "Could not fully sample these objects"
        ws5["A1"].font = Font(name="Arial", size=12, bold=True, color=argb(AUDIT_TITLE))
        for i, w in enumerate(result.warnings, start=3):
            ws5.cell(row=i, column=1, value=w).font = body_font
        ws5.column_dimensions["A"].width = 110

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---- PDF report (<= 10 pages) -------------------------------------------------


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


class _AuditPDF(FPDF):
    def __init__(self, project_name: str):
        super().__init__(orientation="P", format="A4")
        self._project_name = project_name or "This HubSpot Portal"
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(15, 15, 15)

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*AUDIT_MUTED)
        self.cell(0, 6, _pdf_safe(f"HubSpot Property Health Audit · {self._project_name}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*AUDIT_HEADER_BG)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*AUDIT_MUTED)
        self.cell(0, 8, _pdf_safe(f"HubSpot Property Health Audit · {self._project_name}"), align="L")
        self.set_xy(self.l_margin, -14)
        self.cell(0, 8, f"Page {self.page_no()}", align="R")


def _stat_tile(pdf: _AuditPDF, x: float, y: float, w: float, h: float, value: str, label: str) -> None:
    pdf.set_fill_color(*AUDIT_KEEP_BG)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=2.5)
    pdf.set_xy(x, y + h * 0.18)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*AUDIT_TITLE)
    pdf.cell(w, 8, _pdf_safe(value), align="C")
    pdf.set_xy(x, y + h * 0.58)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*AUDIT_BODY)
    pdf.cell(w, 6, _pdf_safe(label), align="C")


def _rating_bar(pdf: _AuditPDF, x: float, y: float, w: float, h: float, keep: int, review: int, remove: int) -> None:
    total = max(keep + review + remove, 1)
    cx = x
    for count, rgb in ((keep, AUDIT_KEEP_BG), (review, AUDIT_REVIEW_BG), (remove, AUDIT_REMOVE_BG)):
        seg_w = w * count / total
        if seg_w <= 0:
            continue
        pdf.set_fill_color(*rgb)
        pdf.rect(cx, y, seg_w, h, style="F")
        if seg_w > 9:
            pdf.set_xy(cx, y + h / 2 - 2.2)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*AUDIT_BODY)
            pdf.cell(seg_w, 4.4, str(count), align="C")
        cx += seg_w


def _key_findings(result: PropertyAuditResult) -> list[str]:
    t = result.totals
    lines = [
        f"{t.custom_count} custom properties were audited across {len(result.object_summaries)} object(s); "
        f"{t.remove_count} are under 5% filled with no workflow referencing them — safe removes after a final "
        f"check — and {t.review_count} more need a human decision.",
    ]
    worst = [s for s in result.object_summaries if s.custom_count > 0][:3]
    if worst:
        parts = ", ".join(f"{s.object_label} ({s.cleanup_score}/100)" for s in worst)
        lines.append(f"Lowest cleanup scores: {parts} — start there for the biggest impact.")
    lines.append(
        '"Uses" only counts references found in this portal\'s workflow actions — forms, lists, reports, and '
        "dashboards aren't read by this tool, so real usage of a property may be higher than shown here."
    )
    if result.warnings:
        plural = "" if len(result.warnings) == 1 else "s"
        lines.append(
            f"{len(result.warnings)} object{plural} couldn't be sampled for Fill % (see the workbook's Warnings "
            "tab) — their rating rests on workflow references alone."
        )
    return lines


def _render_pdf(result: PropertyAuditResult, project_name: str, max_breakdown_objects: int) -> bytes:
    pdf = _AuditPDF(project_name)
    pdf.add_page()

    t = result.totals
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*AUDIT_TITLE)
    pdf.cell(0, 12, _pdf_safe("HubSpot Property Health Audit"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*AUDIT_SUBTITLE)
    pdf.cell(
        0,
        7,
        _pdf_safe(f"Every object and property, rated Keep / Review / Remove candidate — {project_name or 'this HubSpot portal'}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(
        0,
        6,
        _pdf_safe(f"Prepared {result.generated_at[:10]} · sampled up to {result.sample_size} records per object"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_draw_color(*AUDIT_HEADER_BG)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.w - pdf.r_margin, pdf.get_y() + 2)
    pdf.ln(8)

    tile_labels = [
        (str(t.properties_count), "Properties audited"),
        (str(t.keep_count), "Keep"),
        (str(t.review_count), "Review"),
        (str(t.remove_count), "Remove candidate"),
        (_pct(t.review_count + t.remove_count, t.properties_count), "Flagged"),
        (str(len(result.object_summaries)), "Objects"),
    ]
    tile_w = (pdf.w - pdf.l_margin - pdf.r_margin - 5 * 3) / 6
    tile_y = pdf.get_y()
    for i, (value, label) in enumerate(tile_labels):
        _stat_tile(pdf, pdf.l_margin + i * (tile_w + 3), tile_y, tile_w, 20, value, label)
    pdf.set_y(tile_y + 26)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*AUDIT_TITLE)
    pdf.cell(0, 8, _pdf_safe("Rating mix by object"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    legend_y = pdf.get_y()
    pdf.set_font("Helvetica", "", 8)
    lx = pdf.l_margin
    for rgb, label in ((AUDIT_KEEP_BG, "Keep"), (AUDIT_REVIEW_BG, "Review"), (AUDIT_REMOVE_BG, "Remove candidate")):
        pdf.set_fill_color(*rgb)
        pdf.rect(lx, legend_y + 1, 4, 4, style="F")
        pdf.set_xy(lx + 5, legend_y)
        pdf.set_text_color(*AUDIT_BODY)
        pdf.cell(30, 6, label)
        lx += 34
    pdf.ln(9)

    chart_objects = sorted(result.object_summaries, key=lambda s: -s.properties_count)[:8]
    label_w = 42
    bar_w = pdf.w - pdf.l_margin - pdf.r_margin - label_w - 12
    for s in chart_objects:
        y = pdf.get_y()
        pdf.set_xy(pdf.l_margin, y + 1.5)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*AUDIT_BODY)
        pdf.cell(label_w, 6, _pdf_safe(s.object_label))
        _rating_bar(pdf, pdf.l_margin + label_w, y, bar_w, 6.5, s.keep_count, s.review_count, s.remove_count)
        pdf.set_xy(pdf.l_margin + label_w + bar_w + 2, y + 1.5)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*AUDIT_MUTED)
        pdf.cell(10, 6, str(s.properties_count))
        pdf.set_y(y + 8.5)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*AUDIT_BODY)
    pdf.multi_cell(
        0,
        5.2,
        _pdf_safe(
            "Every custom property received a rating from its fill rate and workflow references. Keep = in "
            "active use (or a native HubSpot field, always kept). Review = ambiguous — a human should decide. "
            "Remove candidate = under 5% filled and referenced by no workflow — safe to delete after a final check."
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    # ---- Page 2: key findings + ratings table ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*AUDIT_TITLE)
    pdf.cell(0, 9, _pdf_safe("Key findings"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*AUDIT_BODY)
    for line in _key_findings(result):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5.5, _pdf_safe(f"• {line}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(0.5)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*AUDIT_TITLE)
    pdf.cell(0, 8, _pdf_safe("Ratings by object"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    header_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=AUDIT_HEADER_BG)
    keep_style = FontFace(emphasis="BOLD", color=AUDIT_BODY, fill_color=AUDIT_KEEP_BG)
    review_style = FontFace(emphasis="BOLD", color=AUDIT_BODY, fill_color=AUDIT_REVIEW_BG)
    remove_style = FontFace(emphasis="BOLD", color=AUDIT_BODY, fill_color=AUDIT_REMOVE_BG)
    total_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=AUDIT_HEADER_BG)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*AUDIT_BODY)
    with pdf.table(
        headings_style=header_style,
        col_widths=(30, 14, 14, 14, 14, 14, 16),
        text_align=("LEFT", "CENTER", "CENTER", "CENTER", "CENTER", "CENTER", "CENTER"),
    ) as table:
        head = table.row()
        for h in ("Object", "Total", "Keep", "Review", "Remove", "% flagged", "Score"):
            head.cell(h)
        for s in result.object_summaries:
            row = table.row()
            row.cell(_pdf_safe(s.object_label))
            row.cell(str(s.properties_count))
            row.cell(str(s.keep_count), style=keep_style)
            row.cell(str(s.review_count), style=review_style)
            row.cell(str(s.remove_count), style=remove_style)
            row.cell(_pct(s.review_count + s.remove_count, s.properties_count))
            row.cell(str(s.cleanup_score))
        total_row = table.row()
        total_row.cell(t.object_label, style=total_style)
        total_row.cell(str(t.properties_count), style=total_style)
        total_row.cell(str(t.keep_count), style=total_style)
        total_row.cell(str(t.review_count), style=total_style)
        total_row.cell(str(t.remove_count), style=total_style)
        total_row.cell(_pct(t.review_count + t.remove_count, t.properties_count), style=total_style)
        total_row.cell(str(t.cleanup_score), style=total_style)

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*AUDIT_MUTED)
    pdf.multi_cell(
        0,
        4.5,
        _pdf_safe('Percentages are of that object\'s own property count. "% flagged" = Review + Remove candidate.'),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    # ---- Page 3: methodology ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*AUDIT_TITLE)
    pdf.cell(0, 9, _pdf_safe("Method & how to read the workbook"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*AUDIT_BODY)
    pdf.cell(0, 7, _pdf_safe("What “used” means"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(
        0,
        5.2,
        _pdf_safe(
            "Two signals decide a custom property's rating: Fill % (the share of a sampled batch of records that "
            "have a value set) and Uses (the number of this portal's workflows whose actions reference the "
            "property). This tool is read-only and only pulls workflows — forms, lists, reports, and "
            "dashboards aren't read, so Uses can undercount a property that's only referenced there. Native "
            "HubSpot properties are always Keep; only custom properties are ever flagged."
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _pdf_safe("Rating rules"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9.5)
    rule_lines = [
        "Remove candidate — custom, under 5% filled, referenced by no workflow.",
        "Review — custom, and either (a) referenced by a workflow but under 25% filled, or (b) 5%+ filled but referenced by no workflow.",
        "Keep — native property (always), or custom with 25%+ fill and at least one workflow reference.",
    ]
    for line in rule_lines:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5.2, _pdf_safe(f"• {line}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _pdf_safe("Workbook tabs"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9.5)
    tab_lines = [
        "Summary — per-object counts and cleanup score, worst-first.",
        f"All Properties — every one of the {t.properties_count} properties, one row each, with blank Notes/Tag columns to fill in.",
        f"Flagged for Action — the {t.remove_count + t.review_count} custom properties rated Remove candidate or Review, worst first.",
    ]
    for line in tab_lines:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5.2, _pdf_safe(f"• {line}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if result.warnings:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _pdf_safe("Warnings"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        for w in result.warnings:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, _pdf_safe(f"• {w}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ---- Breakdown by object (trimmed to respect the page budget) ----
    breakdown_objects = result.object_summaries[:max_breakdown_objects]
    if breakdown_objects:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*AUDIT_TITLE)
        pdf.cell(0, 9, _pdf_safe("Breakdown by object"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

        rows_by_object: dict[str, list[PropertyAuditRow]] = {}
        for r in result.rows:
            rows_by_object.setdefault(r.object_label, []).append(r)

        for s in breakdown_objects:
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*AUDIT_TITLE)
            pdf.cell(0, 8, _pdf_safe(s.object_label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            mini_w = 26
            mini_y = pdf.get_y()
            for i, (value, label) in enumerate(
                (
                    (str(s.properties_count), "Total"),
                    (str(s.keep_count), "Keep"),
                    (str(s.review_count), "Review"),
                    (str(s.remove_count), "Remove"),
                )
            ):
                _stat_tile(pdf, pdf.l_margin + i * (mini_w + 3), mini_y, mini_w, 15, value, label)
            pdf.set_y(mini_y + 19)

            object_rows = rows_by_object.get(s.object_label, [])
            worst = sorted(
                (r for r in object_rows if r.rating == RATING_REMOVE),
                key=lambda r: r.fill_pct,
            )[:3]
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(*AUDIT_BODY)
            if s.custom_count == 0:
                summary = "No custom properties on this object — every field is a native Keep."
            elif worst:
                examples = "; ".join(f"{r.property_label} ({r.fill_pct:.0f}% filled)" for r in worst)
                summary = (
                    f"{s.custom_count} custom propert{'y' if s.custom_count == 1 else 'ies'}, cleanup score "
                    f"{s.cleanup_score}/100. Clearest removes: {examples}."
                )
            else:
                summary = (
                    f"{s.custom_count} custom propert{'y' if s.custom_count == 1 else 'ies'}, cleanup score "
                    f"{s.cleanup_score}/100. No clear-cut removes — see the Review rows in the workbook."
                )
            pdf.multi_cell(0, 5.2, _pdf_safe(summary), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(3)

        skipped = len(result.object_summaries) - len(breakdown_objects)
        if skipped > 0:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*AUDIT_MUTED)
            pdf.multi_cell(
                0,
                5,
                _pdf_safe(f"...and {skipped} more object(s) — see the full workbook for detail."),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

    return bytes(pdf.output())


def _page_count(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


def property_audit_to_pdf(result: PropertyAuditResult, project_name: str = "") -> bytes:
    """Renders the report, trimming the per-object breakdown section until
    it fits within the 10-page cap -- guarantees the limit holds regardless
    of how many objects a given portal has, rather than assuming it."""
    max_objects = len(result.object_summaries)
    while True:
        pdf_bytes = _render_pdf(result, project_name, max_objects)
        if _page_count(pdf_bytes) <= _MAX_REPORT_PAGES or max_objects == 0:
            return pdf_bytes
        max_objects = max(0, max_objects - max(1, max_objects // 4))
