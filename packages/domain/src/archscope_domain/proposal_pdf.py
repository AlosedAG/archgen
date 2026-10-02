"""SonaMation-branded PDF for the Proposal & SOW builder (Module 10).

Layout follows the SOW example the builder is based on (parties table,
effective/expiration dates, description of services, deliverables and
milestone schedule, additional services menu, payment, expenses) and
regroups it into the three proposal volumes — Technical, Management,
Cost — with a "Scope at a Glance" page up front so a client can see what
is and isn't included before reading anything else.

Like ``archscope_domain.exporters`` this uses fpdf2's core Helvetica font (no bundled
TTF), so all text goes through ``_pdf_safe`` for Latin-1.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from fpdf import FPDF
from fpdf.enums import TableCellFillMode, XPos, YPos
from fpdf.fonts import FontFace

from archscope_domain.exporters import _pdf_safe
from archscope_domain.proposal import (
    OPTIONAL_SECTIONS,
    SCOPE_CLIENT,
    SCOPE_IN,
    SCOPE_OPTIONAL,
    SCOPE_OUT,
    format_money,
    nonblank,
    number_requirements,
    pricing_summary,
    requirement_coverage,
    scope_by_status,
    to_bool,
    to_float,
)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# SonaMation palette — same values as core.theme (kept as literals here so
# PDF generation doesn't import Streamlit).
PURPLE_DARK = _rgb("#2A2058")
PURPLE = _rgb("#3D2E7C")
PURPLE_LIGHT = _rgb("#5B45B0")
ORANGE = _rgb("#F7791D")
TEXT_DARK = _rgb("#14121F")
TEXT_BODY = _rgb("#3E3A4D")
MUTED = (150, 145, 168)
BG_ALT = _rgb("#F6F5FA")
BORDER = _rgb("#E4E1EE")
WHITE = (255, 255, 255)

# Scope bucket colors: (header fill, light tint, heading, one-line explainer)
SCOPE_STYLE: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], str, str]] = {
    SCOPE_IN: (PURPLE, (228, 224, 245), "INCLUDED", "Delivered under this agreement, up to the stated limit."),
    SCOPE_OUT: (
        (110, 105, 128),
        (238, 236, 242),
        "NOT INCLUDED",
        "Not part of this agreement. Can be added only through a Change Request.",
    ),
    SCOPE_OPTIONAL: (
        ORANGE,
        (253, 232, 214),
        "AVAILABLE AS ADD-ON",
        "Pre-priced options you can add at any time - see the Cost volume.",
    ),
    SCOPE_CLIENT: (PURPLE_LIGHT, (236, 232, 250), "YOUR TEAM PROVIDES", "Client responsibilities the schedule depends on."),
}

HEADER_STYLE = FontFace(emphasis="BOLD", color=WHITE, fill_color=PURPLE)


def _t(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return _pdf_safe(str(value).strip())


class _ProposalPDF(FPDF):
    def __init__(self, proposal: dict[str, Any]):
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.p = proposal
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(18, 18, 18)
        self.set_title(_t(f"{proposal.get('document_type', '')} - {proposal.get('title', '')}"))
        self.set_author(_t(proposal.get("seller", {}).get("company") or "SonaMation"))
        self.alias_nb_pages()

    _skip_next_add_page = False

    def add_page(self, *args: Any, **kwargs: Any) -> None:
        # insert_toc_placeholder() already breaks to a fresh page after the
        # reserved contents page; skip the next section's own add_page() so
        # that fresh page is used instead of left blank.
        if self._skip_next_add_page:
            self._skip_next_add_page = False
            return
        super().add_page(*args, **kwargs)

    def contents_page(self) -> None:
        self.add_page()
        self.insert_toc_placeholder(_render_toc, pages=1)
        self._skip_next_add_page = True

    @property
    def content_w(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(8)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*PURPLE)
        self.cell(40, 5, "SonaMation")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        client = self.p.get("client", {}).get("company") or ""
        label = f"{self.p.get('document_type', '')} - {self.p.get('title', '')}" + (f" - {client}" if client else "")
        self.cell(0, 5, _t(label), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_fill_color(*ORANGE)
        self.rect(self.l_margin, 13.5, 14, 0.9, style="F")
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin + 15, 13.95, self.w - self.r_margin, 13.95)
        self.set_y(self.t_margin)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        ref = self.p.get("reference_number") or ""
        self.cell(0, 5, _t(f"Confidential{'  |  Ref. ' + ref if ref else ''}"), align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    # ---- building blocks ----

    def volume(self, number: str, title: str, lead: str) -> None:
        """Full-width purple band opening one of the three volumes."""
        self.add_page()
        self.start_section(_t(f"{number}. {title}" if number else title), level=0)
        y = self.get_y()
        self.set_fill_color(*PURPLE_DARK)
        self.rect(self.l_margin, y, self.content_w, 26, style="F", round_corners=True, corner_radius=3)
        self.set_fill_color(*ORANGE)
        self.rect(self.l_margin, y, 3, 26, style="F")
        self.set_xy(self.l_margin + 8, y + 4)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*ORANGE)
        self.cell(0, 5, _t(f"VOLUME {number}" if number else "SECTION"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 8)
        self.set_font("Helvetica", "B", 17)
        self.set_text_color(*WHITE)
        self.cell(0, 10, _t(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + 30)
        if lead:
            self.set_font("Helvetica", "I", 9.5)
            self.set_text_color(*TEXT_BODY)
            self.multi_cell(0, 5, _t(lead), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(2)

    def heading(self, title: str, level: int = 1, *, toc: bool = True) -> None:
        if self.get_y() > self.h - 45:
            self.add_page()
        self.ln(3 if level == 1 else 1.5)
        if toc:
            self.start_section(_t(title), level=level)
        if level == 1:
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(*PURPLE)
            self.cell(0, 8, _t(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_fill_color(*ORANGE)
            self.rect(self.l_margin, self.get_y(), 12, 0.9, style="F")
            self.ln(3)
        else:
            self.set_font("Helvetica", "B", 10.5)
            self.set_text_color(*TEXT_DARK)
            self.cell(0, 7, _t(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def para(self, text: str, *, italic: bool = False, size: float = 9.5, empty: str = "") -> None:
        is_placeholder = not (text or "").strip()
        text = empty if is_placeholder else text.strip()
        if not text:
            return
        self.set_font("Helvetica", "I" if italic or is_placeholder else "", size)
        self.set_text_color(*(MUTED if is_placeholder else TEXT_BODY))
        for block in text.split("\n"):
            if block.strip().startswith(("- ", "* ")):
                self.set_x(self.l_margin + 3)
                self.multi_cell(0, 5, _t("- " + block.strip()[2:]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                self.multi_cell(0, 5, _t(block), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)

    def data_table(
        self,
        rows: list[dict[str, Any]],
        columns: list[str],
        widths: tuple[float, ...],
        *,
        align: tuple[str, ...] | None = None,
        empty: str = "None specified.",
        cell_style: Callable[[dict[str, Any], str], FontFace | None] | None = None,
        formatters: dict[str, Callable[[Any], str]] | None = None,
        font_size: float = 8.5,
    ) -> None:
        if not rows:
            self.para(empty, italic=True, empty=empty)
            return
        formatters = formatters or {}
        self.set_font("Helvetica", "", font_size)
        self.set_text_color(*TEXT_BODY)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.set_fill_color(*WHITE)
        with FPDF.table(
            self,
            col_widths=widths,
            headings_style=HEADER_STYLE,
            cell_fill_color=BG_ALT,
            cell_fill_mode=TableCellFillMode.ROWS,
            text_align=align or tuple("LEFT" for _ in columns),
            line_height=4.6,
            padding=1.6,
            first_row_as_headings=True,
        ) as tbl:
            head = tbl.row()
            for col in columns:
                head.cell(_t(col))
            for row in rows:
                r = tbl.row()
                for col in columns:
                    value = formatters[col](row.get(col)) if col in formatters else row.get(col)
                    style = cell_style(row, col) if cell_style else None
                    r.cell(_t(value), style=style)
        self.ln(3)


# ---- Sections -----------------------------------------------------------------


def _cover(pdf: _ProposalPDF) -> None:
    p = pdf.p
    pdf.add_page()
    band_h = 118
    pdf.set_fill_color(*PURPLE_DARK)
    pdf.rect(0, 0, pdf.w, band_h, style="F")
    pdf.set_fill_color(*PURPLE)
    pdf.rect(0, band_h - 26, pdf.w, 26, style="F")
    pdf.set_fill_color(*ORANGE)
    pdf.rect(0, band_h, pdf.w, 2.2, style="F")

    pdf.set_xy(pdf.l_margin, 20)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 8, _t(p.get("seller", {}).get("company") or "SonaMation"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(*ORANGE)
    pdf.rect(pdf.l_margin, pdf.get_y() + 1, 16, 1.2, style="F")

    pdf.set_xy(pdf.l_margin, 44)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 6, _t(str(p.get("document_type", "")).upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*WHITE)
    pdf.multi_cell(pdf.content_w, 11, _t(p.get("title") or "Untitled"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(pdf.l_margin, band_h - 20)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(237, 233, 250)
    client = p.get("client", {}).get("company") or "Client"
    issue = p.get("issue_date") or date.today().isoformat()
    pdf.cell(0, 6, _t(f"Prepared for {client}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _t(f"Issued {issue}" + (f"   |   Ref. {p['reference_number']}" if p.get("reference_number") else "")))

    # Addresses and contacts for notices (SOW page 1)
    pdf.set_y(band_h + 12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*PURPLE)
    pdf.cell(0, 7, "Addresses and contacts for notices", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    client_d, seller_d = p.get("client", {}), p.get("seller", {})
    pairs = [
        ("Company", "company"),
        ("Primary contact", "contact"),
        ("Address", "address"),
        ("Phone", "phone"),
        ("Email", "email"),
    ]
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TEXT_BODY)
    pdf.set_draw_color(*BORDER)
    pdf.set_fill_color(*WHITE)
    with pdf.table(
        col_widths=(26, 57, 57),
        headings_style=HEADER_STYLE,
        cell_fill_color=BG_ALT,
        cell_fill_mode=TableCellFillMode.ROWS,
        line_height=5,
        padding=1.8,
    ) as tbl:
        head = tbl.row()
        head.cell("")
        head.cell("Client")
        head.cell(_t(seller_d.get("company") or "SonaMation"))
        for label, key in pairs:
            r = tbl.row()
            r.cell(label, style=FontFace(emphasis="BOLD", color=TEXT_DARK))
            r.cell(_t(client_d.get(key)))
            r.cell(_t(seller_d.get(key)))
    pdf.ln(5)

    dates = [
        ("Effective date", p.get("effective_date")),
        ("Expiration date", p.get("expiration_date")),
        ("Proposal valid until", p.get("valid_until")),
        ("Reference", p.get("reference_number")),
    ]
    dates = [(label, value) for label, value in dates if str(value or "").strip()]
    if dates:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_fill_color(*WHITE)
        with pdf.table(col_widths=(40, 100), line_height=5, padding=1.8, first_row_as_headings=False) as tbl:
            for label, value in dates:
                r = tbl.row()
                r.cell(_t(label), style=FontFace(emphasis="BOLD", color=WHITE, fill_color=PURPLE))
                r.cell(_t(value))


def _render_toc(pdf: FPDF, outline: list[Any]) -> None:
    pdf.set_xy(pdf.l_margin, pdf.t_margin)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*PURPLE)
    pdf.cell(0, 10, "Contents", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(*ORANGE)
    pdf.rect(pdf.l_margin, pdf.get_y(), 12, 0.9, style="F")
    pdf.ln(5)
    for entry in outline:
        if entry.level > 1:
            continue
        indent = 0 if entry.level == 0 else 6
        pdf.set_font("Helvetica", "B" if entry.level == 0 else "", 10 if entry.level == 0 else 9)
        pdf.set_text_color(*(TEXT_DARK if entry.level == 0 else TEXT_BODY))
        if entry.level == 0:
            pdf.ln(1.5)
        pdf.set_x(pdf.l_margin + indent)
        width = pdf.w - pdf.l_margin - pdf.r_margin - indent - 12
        pdf.cell(width, 5.6, _t(entry.name), link=pdf.add_link(page=entry.page_number))
        pdf.cell(12, 5.6, str(entry.page_number), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _scope_at_a_glance(pdf: _ProposalPDF) -> None:
    p = pdf.p
    groups = scope_by_status(p)
    totals = pricing_summary(p)
    currency = p.get("currency", "USD")

    pdf.add_page()
    pdf.start_section("Scope at a Glance", level=0)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*PURPLE)
    pdf.cell(0, 10, "Scope at a Glance", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(*ORANGE)
    pdf.rect(pdf.l_margin, pdf.get_y(), 12, 0.9, style="F")
    pdf.ln(3)
    pdf.para(
        "Every item a client might ask about sits in exactly one of the lists below. If something is not "
        "listed as Included, it is not part of this agreement - it can still be added through the Change "
        "Request process described in the Technical volume. Item IDs (S-01, S-02...) are the reference to use "
        "when asking about scope."
    )

    tiles = [
        (str(len(groups[SCOPE_IN])), "Included items"),
        (str(len(groups[SCOPE_OUT])), "Excluded items"),
        (str(len(groups[SCOPE_OPTIONAL])), "Optional add-ons"),
        (format_money(totals["total"], currency), "Total one-time fee"),
    ]
    gap = 3
    tile_w = (pdf.content_w - gap * (len(tiles) - 1)) / len(tiles)
    y = pdf.get_y() + 1
    for i, (value, label) in enumerate(tiles):
        x = pdf.l_margin + i * (tile_w + gap)
        pdf.set_fill_color(*BG_ALT)
        pdf.rect(x, y, tile_w, 18, style="F", round_corners=True, corner_radius=2.5)
        pdf.set_fill_color(*(ORANGE if i == len(tiles) - 1 else PURPLE))
        pdf.rect(x, y, tile_w, 1.2, style="F")
        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*PURPLE_DARK)
        pdf.cell(tile_w, 7, _t(value), align="C")
        pdf.set_xy(x, y + 10.5)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*TEXT_BODY)
        pdf.cell(tile_w, 5, _t(label), align="C")
    pdf.set_y(y + 23)

    addon_prices = {str(a.get("Service", "")).strip().lower(): a for a in nonblank(p.get("addons", []), "Service")}
    for status in (SCOPE_IN, SCOPE_OUT, SCOPE_OPTIONAL, SCOPE_CLIENT):
        items = groups[status]
        if status == SCOPE_CLIENT and not items:
            continue
        fill, tint, heading, explainer = SCOPE_STYLE[status]
        if pdf.get_y() > pdf.h - 45:
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_fill_color(*fill)
        pdf.rect(pdf.l_margin, y, pdf.content_w, 7.5, style="F", round_corners=True, corner_radius=1.5)
        pdf.set_xy(pdf.l_margin + 3, y + 1.2)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*WHITE)
        pdf.cell(60, 5, _t(f"{heading}  ({len(items)})"))
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(pdf.content_w - 66, 5, _t(explainer), align="R")
        pdf.set_y(y + 9)

        if not items:
            pdf.set_x(pdf.l_margin + 3)
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(*MUTED)
            pdf.cell(0, 5, "Nothing listed.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
            continue

        for item in items:
            detail = str(item.get("Quantity / Limit") or "").strip()
            if status == SCOPE_OPTIONAL:
                addon = addon_prices.get(str(item.get("Item", "")).strip().lower())
                if addon:
                    price = f"{format_money(to_float(addon.get('Cost')), currency)} {addon.get('Billing', '')}".strip()
                    detail = f"{detail}  |  {price}" if detail else price
            text = str(item.get("Item") or "")
            if item.get("Workstream"):
                text = f"{item['Workstream']}: {text}"
            id_w, detail_w, lh = 14, (52 if detail else 0), 5.2
            text_w = pdf.content_w - id_w - detail_w
            pdf.set_font("Helvetica", "", 8.5)
            text_lines: list[str] = pdf.multi_cell(text_w - 2, lh, _t(text), dry_run=True, output="LINES")  # type: ignore[assignment]  # fpdf2 types output= as a union
            pdf.set_font("Helvetica", "I", 8)
            detail_lines: list[str] = pdf.multi_cell(detail_w - 2, lh, _t(detail), dry_run=True, output="LINES") if detail else []  # type: ignore[assignment]
            row_h = max(len(text_lines), len(detail_lines), 1) * lh + 1.6
            if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
                pdf.add_page()
            row_y = pdf.get_y()
            pdf.set_fill_color(*tint)
            pdf.rect(pdf.l_margin, row_y, pdf.content_w, row_h, style="F")
            pdf.set_xy(pdf.l_margin + 1, row_y + 0.8)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*fill)
            pdf.cell(id_w - 1, lh, _t(item.get("ID")))
            pdf.set_xy(pdf.l_margin + id_w, row_y + 0.8)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*TEXT_DARK)
            pdf.multi_cell(text_w - 2, lh, _t(text))
            if detail:
                pdf.set_xy(pdf.l_margin + id_w + text_w, row_y + 0.8)
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*TEXT_BODY)
                pdf.multi_cell(detail_w - 2, lh, _t(detail), align="R")
            pdf.set_y(row_y + row_h + 0.8)
        pdf.ln(2.5)


def _technical(pdf: _ProposalPDF, sections: dict[str, bool]) -> None:
    p = pdf.p
    pdf.volume(
        "I",
        "Technical Approach",
        "Our understanding of the problem, the proposed solution, and the specific tools, techniques and "
        "procedures SonaMation will use to implement it - including the detailed scope of work.",
    )
    pdf.heading("1.1 Understanding of the Problem")
    pdf.para(p.get("problem_statement", ""), empty="To be completed.")
    if (p.get("current_state") or "").strip():
        pdf.heading("Current state", level=2)
        pdf.para(p["current_state"])

    pdf.heading("1.2 Objectives")
    pdf.data_table(nonblank(p.get("objectives", []), "Objective"), ["Objective", "Success Measure"], (95, 65))

    pdf.heading("1.3 Requirements")
    pdf.para(
        "Requirements the solution must satisfy. Each one is traced to the scope items that deliver it (section 1.8).", size=9
    )
    reqs = number_requirements(nonblank(p.get("requirements", []), "Requirement"))
    pdf.data_table(reqs, ["ID", "Requirement", "Priority", "Source"], (14, 92, 22, 32))

    pdf.heading("1.4 Proposed Solution")
    pdf.para(p.get("solution_overview", ""), empty="To be completed.")

    pdf.heading("1.5 Methodology")
    pdf.data_table(nonblank(p.get("methodology", []), "Phase"), ["Phase", "Activities", "Outputs"], (40, 72, 48))

    pdf.heading("1.6 Tools & Platforms")
    pdf.data_table(nonblank(p.get("tools", []), "Tool / Platform"), ["Tool / Platform", "Purpose", "Provided By"], (48, 86, 26))

    pdf.heading("1.7 Techniques & Procedures")
    pdf.data_table(
        nonblank(p.get("techniques", []), "Technique / Procedure"), ["Technique / Procedure", "How It Is Applied"], (50, 110)
    )

    groups = scope_by_status(p)
    pdf.heading("1.8 Detailed Scope of Work")
    pdf.para(
        "The table below is the complete list of work included in this agreement. Quantities are upper limits; "
        "each item is complete when it meets its acceptance criteria.",
        size=9,
    )
    pdf.data_table(
        groups[SCOPE_IN],
        ["ID", "Workstream", "Item", "Quantity / Limit", "Tools / Techniques", "Acceptance Criteria", "Req. ID"],
        (12, 22, 38, 20, 26, 30, 12),
        font_size=7.8,
        empty="No items are marked In Scope yet.",
    )

    pdf.heading("Out of scope", level=2)
    pdf.para("Explicitly excluded. Any of these can be added through a Change Request.", size=9)
    pdf.data_table(groups[SCOPE_OUT], ["ID", "Workstream", "Item", "Quantity / Limit"], (14, 34, 82, 30), font_size=8)

    if groups[SCOPE_CLIENT]:
        pdf.heading("Client responsibilities", level=2)
        pdf.data_table(groups[SCOPE_CLIENT], ["ID", "Item", "Quantity / Limit", "Milestone"], (14, 96, 28, 22), font_size=8)

    if groups[SCOPE_OPTIONAL]:
        pdf.heading("Optional add-ons", level=2)
        pdf.para("Available at the prices in the Cost volume; not included unless selected.", size=9)
        pdf.data_table(groups[SCOPE_OPTIONAL], ["ID", "Workstream", "Item", "Quantity / Limit"], (14, 34, 82, 30), font_size=8)

    pdf.heading("Requirements traceability", level=2)
    coverage = requirement_coverage(p)

    def _coverage_style(row: dict[str, Any], col: str) -> FontFace | None:
        if col != "Coverage":
            return None
        if row["Coverage"] == "Covered":
            return FontFace(emphasis="BOLD", color=PURPLE)
        if row["Coverage"] == "Not covered":
            return FontFace(emphasis="BOLD", color=ORANGE)
        return FontFace(emphasis="BOLD", color=TEXT_BODY)

    pdf.data_table(
        coverage, ["ID", "Requirement", "Scope Items", "Coverage"], (14, 94, 26, 26), cell_style=_coverage_style, font_size=8
    )

    pdf.heading("1.9 Assumptions")
    for row in nonblank(p.get("assumptions", []), "Assumption"):
        pdf.para(f"- {row['Assumption']}", size=9)

    pdf.heading("1.10 Change Request Process")
    pdf.para(p.get("change_process", ""))

    glossary = nonblank(p.get("glossary", []), "Term")
    if sections.get("glossary") and glossary:
        pdf.heading("1.11 Glossary of Terms")
        pdf.data_table(glossary, ["Term", "Definition"], (42, 118))


def _management(pdf: _ProposalPDF, sections: dict[str, bool]) -> None:
    p = pdf.p
    pdf.volume(
        "II",
        "Management Approach",
        "How SonaMation will manage contract performance: who is involved, how progress is reported, the "
        "schedule, how risks are handled, and how deliverables are accepted.",
    )
    pdf.heading("2.1 Project Team & Roles")
    pdf.data_table(
        nonblank(p.get("team", []), "Name", "Role"), ["Side", "Role", "Name", "Email", "Responsibilities"], (22, 32, 32, 38, 36)
    )

    pdf.heading("2.2 Governance & Communication")
    pdf.data_table(
        nonblank(p.get("governance", []), "Meeting / Report"),
        ["Meeting / Report", "Cadence", "Participants", "Purpose"],
        (36, 24, 38, 62),
    )

    pdf.heading("2.3 Schedule")
    pdf.data_table(
        nonblank(p.get("timeline", []), "Phase / Milestone"),
        ["Phase / Milestone", "Start", "End", "Key Deliverables"],
        (50, 22, 22, 66),
    )

    n = 4
    if sections.get("risks"):
        pdf.heading(f"2.{n} Risk Management")
        n += 1
        pdf.data_table(
            nonblank(p.get("risks", []), "Risk"), ["Risk", "Likelihood", "Impact", "Mitigation", "Owner"], (50, 18, 16, 54, 22)
        )
    if sections.get("kpis"):
        pdf.heading(f"2.{n} Targeted KPIs")
        n += 1
        pdf.para(
            "Primary KPIs are the value drivers tied to return on investment; secondary KPIs track operational improvement.",
            size=9,
        )
        pdf.data_table(nonblank(p.get("kpis", []), "KPI"), ["KPI", "Type", "Definition", "Target"], (40, 18, 72, 30))
    pdf.heading(f"2.{n} Acceptance Process")
    pdf.para(p.get("acceptance_process", ""))


def _cost(pdf: _ProposalPDF, sections: dict[str, bool]) -> None:
    p = pdf.p
    currency = p.get("currency", "USD")
    money = lambda v: format_money(to_float(v), currency)  # noqa: E731
    totals = pricing_summary(p)

    pdf.volume(
        "III",
        "Cost & Pricing",
        "What the proposed work costs, when it is invoiced, and the price of anything beyond the agreed scope.",
    )
    pdf.heading("3.1 Deliverables & Milestone Schedule")
    milestones = nonblank(p.get("milestones", []), "Milestone")
    total_row = {
        "Milestone": "Total",
        "Deliverables": "",
        "Start On or Before": "",
        "Due On or Before": "",
        "Fee": totals["milestone_total"],
        "_total": True,
    }

    def _ms_style(row: dict[str, Any], col: str) -> FontFace | None:
        if row.get("_total"):
            return FontFace(emphasis="BOLD", color=WHITE, fill_color=PURPLE_DARK)
        if col == "Milestone":
            return FontFace(emphasis="BOLD", color=TEXT_DARK)
        return None

    pdf.data_table(
        milestones + ([total_row] if milestones else []),
        ["Milestone", "Deliverables", "Start On or Before", "Due On or Before", "Fee"],
        (34, 62, 22, 22, 20),
        align=("LEFT", "LEFT", "LEFT", "LEFT", "RIGHT"),
        formatters={"Fee": money},
        cell_style=_ms_style,
    )

    addons = nonblank(p.get("addons", []), "Service")
    n = 2
    if sections.get("addons") and addons:
        pdf.heading(f"3.{n} Optional Add-on Services Menu")
        n += 1
        pdf.para(
            "Pre-priced services the client can add to this agreement at any time. Items marked Selected are included in the total below.",
            size=9,
        )
        rows = [{**a, "Selected": "Selected" if to_bool(a.get("Add to Total")) else ""} for a in addons]
        pdf.data_table(
            rows,
            ["Service", "Includes", "Cost", "Billing", "Selected"],
            (40, 66, 20, 18, 16),
            align=("LEFT", "LEFT", "RIGHT", "LEFT", "CENTER"),
            formatters={"Cost": money},
            cell_style=lambda r, c: FontFace(emphasis="BOLD", color=ORANGE) if c == "Selected" else None,
        )

    rates = nonblank(p.get("rate_card", []), "Role")
    if sections.get("rate_card") and rates:
        pdf.heading(f"3.{n} Rate Card")
        n += 1
        pdf.para("Used to price approved Change Requests that are not on the add-on menu.", size=9)
        pdf.data_table(rates, ["Role", "Hourly Rate"], (110, 50), align=("LEFT", "RIGHT"), formatters={"Hourly Rate": money})

    pdf.heading(f"3.{n} Pricing Summary")
    n += 1
    summary = [{"Item": "Milestone fees", "Amount": totals["milestone_total"]}]
    if totals["selected_addons_one_time"]:
        summary.append({"Item": "Selected one-time add-ons", "Amount": totals["selected_addons_one_time"]})
    if totals["discount"]:
        summary.append({"Item": f"Discount ({totals['discount_pct']:g}%)", "Amount": -totals["discount"]})
    summary.append({"Item": "Total one-time fee", "Amount": totals["total"], "_total": True})
    for billing, amount in totals["recurring"].items():
        summary.append({"Item": f"Selected recurring add-ons ({billing})", "Amount": amount})
    pdf.data_table(
        summary,
        ["Item", "Amount"],
        (110, 50),
        align=("LEFT", "RIGHT"),
        formatters={"Amount": money},
        cell_style=lambda r, c: FontFace(emphasis="BOLD", color=WHITE, fill_color=PURPLE_DARK) if r.get("_total") else None,
    )

    pdf.heading(f"3.{n} Payment Terms")
    n += 1
    pdf.para(p.get("payment_terms", ""))
    pdf.heading(f"3.{n} Expenses")
    pdf.para(p.get("expenses", ""))


def _signatures(pdf: _ProposalPDF) -> None:
    p = pdf.p
    if pdf.get_y() > pdf.h - 90:
        pdf.add_page()
    pdf.heading("Acceptance & Signatures")
    pdf.para(
        f"By signing below, the parties agree to this {p.get('document_type', 'agreement')}, including the scope, "
        "exclusions, assumptions and fees described above, effective as of the effective date.",
        size=9,
    )
    pdf.ln(2)
    gap = 10
    w = (pdf.content_w - gap) / 2
    y = pdf.get_y()
    for i, party in enumerate(
        (p.get("client", {}).get("company") or "Client", p.get("seller", {}).get("company") or "SonaMation")
    ):
        x = pdf.l_margin + i * (w + gap)
        pdf.set_fill_color(*BG_ALT)
        pdf.rect(x, y, w, 58, style="F", round_corners=True, corner_radius=2.5)
        pdf.set_fill_color(*(PURPLE if i == 0 else ORANGE))
        pdf.rect(x, y, w, 1.2, style="F")
        pdf.set_xy(x + 5, y + 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*PURPLE_DARK)
        pdf.cell(w - 10, 6, _t(party))
        for j, label in enumerate(("Signature", "Name", "Title", "Date")):
            ly = y + 20 + j * 10
            pdf.set_draw_color(*MUTED)
            pdf.line(x + 5, ly, x + w - 5, ly)
            pdf.set_xy(x + 5, ly + 0.5)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*MUTED)
            pdf.cell(w - 10, 4, label)
    pdf.set_y(y + 64)


def proposal_to_pdf(proposal: dict[str, Any]) -> bytes:
    sections = {key: bool(proposal.get("sections", {}).get(key, True)) for key in OPTIONAL_SECTIONS}
    pdf = _ProposalPDF(proposal)

    _cover(pdf)
    pdf.contents_page()

    if sections["executive_summary"] and (proposal.get("executive_summary") or "").strip():
        pdf.add_page()
        pdf.start_section("Executive Summary", level=0)
        pdf.heading("Executive Summary", toc=False)
        pdf.para(proposal["executive_summary"])
        if sections["company_overview"]:
            pdf.heading("About SonaMation")
            pdf.para(proposal.get("company_overview", ""))
    elif sections["company_overview"] and (proposal.get("company_overview") or "").strip():
        pdf.add_page()
        pdf.start_section("About SonaMation", level=0)
        pdf.heading("About SonaMation", toc=False)
        pdf.para(proposal["company_overview"])

    _scope_at_a_glance(pdf)
    _technical(pdf, sections)
    _management(pdf, sections)
    _cost(pdf, sections)

    pdf.add_page()
    pdf.start_section("Terms & Acceptance", level=0)
    pdf.heading("Confidentiality")
    pdf.para(proposal.get("confidentiality", ""))
    if sections["signatures"]:
        _signatures(pdf)

    return bytes(pdf.output())
