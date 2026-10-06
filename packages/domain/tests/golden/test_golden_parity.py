"""Golden parity: every domain output, pinned to what the Streamlit-era
code produced before the platform rebuild moved it.

Each case runs a domain entry point on fixed inputs and compares a
normalized, JSON-serializable view of the result with
``fixtures/<case>.json``. Structured outputs are compared field by field;
binary documents (.docx/.xlsx/.pdf) are compared on their extracted text
and cell values, since their bytes embed creation timestamps.

Regenerate fixtures ONLY when an output change is intended::

    GOLDEN_UPDATE=1 pytest tests/golden

and review the fixture diff like any other code change.
"""

from __future__ import annotations

import dataclasses
import io
import json
import os
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

FIXTURES = Path(__file__).parent / "fixtures"
UPDATE = os.environ.get("GOLDEN_UPDATE") == "1"

_TIMESTAMP_KEYS = {"generated_at", "pulled_at"}
_TODAY_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%B %-d, %Y" if os.name != "nt" else "%B %#d, %Y", "%d %B %Y", "%b %d, %Y")


# ---- normalization ------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Dataclasses/tuples/sets -> JSON-compatible structures, with
    run-time timestamps masked so fixtures are stable across runs."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): ("<TIMESTAMP>" if k in _TIMESTAMP_KEYS and v else _plain(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, str):
        return _mask_today(value)
    # Numbers pass through untouched: JSON keeps 14000.0 distinct from 14000,
    # so an int/float drift in pricing math fails parity too.
    return value


def _mask_today(text: str) -> str:
    # Full run-time timestamps first, before the date inside them is masked.
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)?", "<TIMESTAMP>", text)
    today = date.today()
    for fmt in _TODAY_FORMATS:
        text = text.replace(today.strftime(fmt), "<TODAY>")
    return text


def _docx_text(data: bytes | io.BytesIO) -> list[str]:
    buffer = data if isinstance(data, io.BytesIO) else io.BytesIO(data)
    doc = Document(buffer)
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return [_mask_today(line) for line in lines]


def _pdf_text(data: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(data))
    return [_mask_today(page.extract_text() or "") for page in reader.pages]


def _xlsx_cells(data: bytes) -> dict[str, list[list[Any]]]:
    workbook = load_workbook(io.BytesIO(data), data_only=False)
    return {
        sheet.title: [[_plain(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        for sheet in workbook.worksheets
    }


# ---- cases ------------------------------------------------------------------------
# Imports live inside each case so the module list reads as the inventory of
# domain entry points under parity, and so one broken import fails one case.


def _blueprint():
    from archscope_domain.blueprint import BlueprintGenerator
    from archscope_domain.models import BlueprintInput
    from archscope_domain.rules import RulesEngine

    raw = json.loads((Path(__file__).resolve().parents[4] / "sample_inputs" / "example_project.json").read_text("utf-8"))
    return BlueprintGenerator(RulesEngine()).generate(BlueprintInput(**raw))


def case_blueprint() -> Any:
    from archscope_domain.blueprint import blueprint_to_json, blueprint_to_markdown

    bp = _blueprint()
    return {
        "blueprint": _plain(bp),
        "json": _plain(json.loads(blueprint_to_json(bp))),
        "markdown": _mask_today(blueprint_to_markdown(bp)),
    }


def _audit_findings():
    from test_audit import FakeHubSpotClient, _dirty_snapshot

    from archscope_domain.audit import PortalAuditor
    from archscope_domain.rules import RulesEngine

    snapshot = _dirty_snapshot()
    return snapshot, PortalAuditor(FakeHubSpotClient(), RulesEngine()).run(snapshot)


def case_audit() -> Any:
    from archscope_domain.audit import findings_to_csv, findings_to_markdown

    _, findings = _audit_findings()
    return {
        "findings": _plain(findings),
        "markdown": findings_to_markdown(findings),
        "csv": findings_to_csv(findings).splitlines(),
    }


def case_property_audit() -> Any:
    from test_property_audit import FakeHubSpotClient, _snapshot

    from archscope_domain.property_audit import property_audit_to_pdf, property_audit_to_xlsx, run_property_audit

    client = FakeHubSpotClient({"email": 1.0, "dead_prop": 0.0, "referenced_prop": 0.1})
    result = run_property_audit(client, _snapshot())
    return {
        "result": _plain(result),
        "xlsx": _xlsx_cells(property_audit_to_xlsx(result, "Golden")),
        "pdf": _pdf_text(property_audit_to_pdf(result, "Golden")),
    }


def case_report() -> Any:
    from test_report import _findings, _snapshot

    from archscope_domain.report import build_report_context, report_to_client_docx, report_to_internal_docx

    audited = build_report_context(_snapshot(), _findings(), project_name="Golden")
    unaudited = build_report_context(_snapshot(), None, project_name="Golden")
    return {
        "context": _plain(audited),
        "context_unaudited": _plain(unaudited),
        "client_docx": _docx_text(report_to_client_docx(audited)),
        "internal_docx": _docx_text(report_to_internal_docx(audited)),
    }


def case_diagram() -> Any:
    from archscope_domain.diagram import (
        dangling_edges,
        diagram_to_json,
        findings_by_area,
        findings_by_severity,
        from_blueprint,
        from_snapshot,
        to_drawio_xml,
        to_graphviz,
    )

    bp_nodes, bp_edges = from_blueprint(_blueprint())
    snapshot, findings = _audit_findings()
    snap_nodes, snap_edges = from_snapshot(snapshot, findings)
    eng_nodes, eng_edges = from_snapshot(snapshot, findings, include_engagements=True)
    return {
        "from_blueprint": _plain(json.loads(diagram_to_json(bp_nodes, bp_edges))),
        "from_snapshot": _plain(json.loads(diagram_to_json(snap_nodes, snap_edges))),
        "from_snapshot_engagements": _plain(json.loads(diagram_to_json(eng_nodes, eng_edges))),
        "dangling": _plain(dangling_edges(bp_nodes, bp_edges)),
        "by_severity": findings_by_severity(findings),
        "by_area": findings_by_area(findings),
        "dot": to_graphviz(bp_nodes, bp_edges).splitlines(),
        "dot_unlabeled": to_graphviz(snap_nodes, snap_edges, show_labels=False).splitlines(),
        "drawio": to_drawio_xml(bp_nodes, bp_edges).splitlines(),
    }


def case_docgen() -> Any:
    from test_docgen import FakeHubSpotClient

    from archscope_domain.docgen import DocumentationGenerator, snapshot_to_docx, snapshot_to_markdown

    snapshot = DocumentationGenerator(FakeHubSpotClient()).build_snapshot()
    return {
        "snapshot": _plain(snapshot),
        "markdown": _mask_today(snapshot_to_markdown(snapshot)).splitlines(),
        "docx": _docx_text(snapshot_to_docx(snapshot)),
    }


def _proposal() -> dict[str, Any]:
    from archscope_domain.proposal import (
        ADDON_LIBRARY,
        BLANK_ROWS,
        SCOPE_LIBRARY,
        SCOPE_OUT,
        add_library_addons,
        add_library_items,
        default_proposal,
        import_from_jep,
        import_from_wrd,
        scope_from_requirements,
    )

    p = default_proposal()
    p["issue_date"] = "2026-09-01"
    p = import_from_wrd(
        p,
        {
            "Project Overview": [{"Field": "Purpose", "Value": "Replace spreadsheets"}],
            "Goals": [{"Goal": "One source of truth"}],
            "Customer Requirements": [{"Requirement": "Sync contacts nightly"}, {"Requirement": "Log SMS"}],
            "Project Definitions": [{"Term": "Member", "Definition": "Paying customer"}],
            "Known Challenges or Risks": [{"Type": "Risk", "Description": "Dirty data"}],
            "Project Plan": [
                {"Milestone": "Go live", "Related Requirement": "1", "Target Date": "2026-12-01 00:00:00", "Status": ""}
            ],
            "Open Questions": [{"Question": "Which ERP?"}],
        },
    )
    p = import_from_jep(
        p,
        {
            "Solutions Partner Contact": [{"Field": "Contact Name", "Value": "Aylin"}],
            "Team Members": [{"Side": "Prospect", "Role": "Sponsor", "Team Member": "Jane", "Email": "j@acme.com"}],
            "Technical Needs": [{"Functionality": "ERP sync", "Confirmed": "True"}],
            "Business Needs": [{"Functionality": "Forecasting", "Confirmed": "False"}],
            "Milestones": [{"Milestone": "Demo", "Target Date": "2026-10-01"}],
            "Questions": [],
        },
        prospect_name="Acme",
    )
    p = add_library_items(p, [SCOPE_LIBRARY[0]["Item"], SCOPE_LIBRARY[1]["Item"]])
    p = add_library_items(p, [SCOPE_LIBRARY[2]["Item"]], SCOPE_OUT)
    p = add_library_addons(p, [ADDON_LIBRARY[0]["Service"]])
    p = scope_from_requirements(p)
    p["milestones"] = [
        {**BLANK_ROWS["milestones"], "Milestone": "M1", "Fee": 11500},
        {**BLANK_ROWS["milestones"], "Milestone": "M2", "Fee": "2,500"},
        {**BLANK_ROWS["milestones"], "Milestone": "", "Fee": 999},
    ]
    p["addons"] += [
        {"Service": "Support", "Includes": "", "Cost": 500, "Billing": "Monthly", "Add to Total": True},
        {"Service": "SEO", "Includes": "", "Cost": "2,500.50", "Billing": "One Time", "Add to Total": False},
    ]
    p["discount_pct"] = 12.5
    return p


def case_proposal() -> Any:
    from archscope_domain.proposal import (
        as_template,
        default_proposal,
        format_money,
        pricing_summary,
        requirement_coverage,
        scope_by_status,
        to_float,
        to_json,
        validate,
    )
    from archscope_domain.proposal_pdf import proposal_to_pdf

    p = _proposal()
    return {
        "proposal": _plain(p),
        "pricing": _plain(pricing_summary(p)),
        "scope_by_status": _plain(scope_by_status(p)),
        "coverage": _plain(requirement_coverage(p)),
        "validate": validate(p),
        "validate_default": validate(default_proposal()),
        "template": _plain(as_template(p)),
        "json": _plain(json.loads(to_json(p))),
        "money": [format_money(v, c) for v, c in [(1234.5, "USD"), (-99.999, "USD"), (0, "EUR"), (1e6, "GBP")]],
        "to_float": [to_float(v) for v in ["$1,234.50", "", None, "abc", 7, "(12)", "1e3"]],
        "pdf": _pdf_text(proposal_to_pdf(p)),
    }


def case_discovery() -> Any:
    from archscope_domain.discovery import (
        build_business_analysis_input,
        build_client_explainer_input,
        build_request,
        empty_notes,
        suggest_modules,
    )

    notes = empty_notes()
    notes["Goals"]["answers"]["kpis"] = {
        "selected": ["Win rate", "Other (specify)"],
        "other": "demo-to-close",
        "notes": "25%",
        "flagged": False,
    }
    notes["Goals"]["answers"]["timeline"] = {"selected": ["1–3 months"], "other": "", "notes": "", "flagged": True}
    notes["Goals"]["answers"]["long_term_goals"] = {"selected": [], "other": "", "notes": "open 3 clinics", "flagged": False}
    notes["Data"]["answers"]["data_regions"] = {
        "selected": ["EU / UK", "United States"],
        "other": "",
        "notes": "",
        "flagged": False,
    }
    notes["Data"]["edge_cases"] = "Two legal entities"
    notes["Processes"]["answers"]["pain_points"] = "legacy free text answer"
    ba = build_business_analysis_input(notes, client_name="Bright Smiles", business_type="dental")
    ce = build_client_explainer_input(["Sales Hub", "Service Hub"], business_type="dental")
    request = build_request(ba, model="claude-opus-5-5")
    md = "## Recommended HubSpot Modules\n- **Sales Hub** — pipelines\n- Ops hub: ERP sync\n## Open Questions & Gaps\n- Marketing"
    return {
        "business_analysis": ba,
        "client_explainer": ce,
        "request": {k: v for k, v in request.items() if k != "system"},
        "system_prompt_len": len(request["system"][0]["text"]),
        "suggest_modules": suggest_modules(md),
    }


def case_exporters() -> Any:
    from test_exporters import SECTIONS

    from archscope_domain.exporters import (
        markdown_to_docx,
        markdown_to_pdf,
        sections_to_csv,
        sections_to_docx,
        sections_to_pdf,
        sections_to_xlsx,
    )

    md = "# Title\n## Section — one\n- bullet → arrow · middot\n**bold** text\n### Sub\nPlain “quoted” paragraph."
    return {
        "docx": _docx_text(sections_to_docx("Golden WRD", "Sub", SECTIONS)),
        "xlsx": _xlsx_cells(sections_to_xlsx(SECTIONS)),
        "csv": sections_to_csv(SECTIONS).splitlines(),
        "pdf": _pdf_text(sections_to_pdf("Golden WRD", "Sub", SECTIONS)),
        "md_docx": _docx_text(markdown_to_docx(md, title="Doc")),
        "md_pdf": _pdf_text(markdown_to_pdf(md, title="Doc")),
    }


def case_rules() -> Any:
    from archscope_domain.rules import RulesEngine

    engine = RulesEngine()
    return {"rules": _plain(engine._rules)}


CASES: dict[str, Callable[[], Any]] = {
    name.removeprefix("case_"): fn for name, fn in sorted(globals().items()) if name.startswith("case_")
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_golden_parity(case: str) -> None:
    actual = json.loads(json.dumps(CASES[case](), ensure_ascii=False, sort_keys=True, default=str))
    path = FIXTURES / f"{case}.json"
    if UPDATE:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(actual, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        pytest.skip(f"golden fixture written: {path.name}")
    assert path.exists(), f"missing fixture {path.name} — run GOLDEN_UPDATE=1 pytest tests/golden"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected
