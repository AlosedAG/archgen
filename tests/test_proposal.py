"""Tests for the Proposal & SOW builder's pure logic (core.proposal) and
its PDF renderer (core.proposal_pdf)."""

from __future__ import annotations

import io

from pypdf import PdfReader

from core.proposal import (
    ADDON_LIBRARY,
    BLANK_ROWS,
    SCOPE_CLIENT,
    SCOPE_IN,
    SCOPE_LIBRARY,
    SCOPE_OPTIONAL,
    SCOPE_OUT,
    add_library_addons,
    add_library_items,
    as_template,
    default_proposal,
    format_money,
    from_json,
    import_from_jep,
    import_from_wrd,
    pricing_summary,
    requirement_coverage,
    scope_by_status,
    scope_from_requirements,
    to_float,
    to_json,
    validate,
)
from core.proposal_pdf import proposal_to_pdf


def _scope(item, status=SCOPE_IN, **extra):
    return {**BLANK_ROWS["scope"], "Item": item, "Status": status, **extra}


def _pdf_text(pdf_bytes: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


def test_to_float_accepts_formatted_money_and_blanks():
    assert to_float("$1,500.50") == 1500.5
    assert to_float("") == 0.0
    assert to_float(None) == 0.0
    assert to_float(float("nan")) == 0.0
    assert to_float("n/a") == 0.0


def test_format_money_puts_sign_before_symbol():
    assert format_money(-1750) == "-$1,750.00"
    assert format_money(12.5, "EUR") == "12.50 EUR"


def test_scope_by_status_numbers_items_and_drops_blank_rows():
    p = default_proposal()
    p["scope"] = [_scope("Workflows"), _scope(""), _scope("Migration", SCOPE_OUT), _scope("Access", SCOPE_CLIENT, ID="S-09")]
    groups = scope_by_status(p)
    assert [i["ID"] for i in groups[SCOPE_IN]] == ["S-01"]
    assert [i["ID"] for i in groups[SCOPE_OUT]] == ["S-02"]
    assert [i["ID"] for i in groups[SCOPE_CLIENT]] == ["S-09"]
    assert groups[SCOPE_OPTIONAL] == []


def test_unknown_status_counts_as_in_scope_rather_than_vanishing():
    p = default_proposal()
    p["scope"] = [_scope("Mystery", "Maybe")]
    assert len(scope_by_status(p)[SCOPE_IN]) == 1


def test_requirement_coverage_only_flags_requirements_no_scope_item_cites():
    p = default_proposal()
    p["requirements"] = [
        {"ID": rid, "Requirement": f"Req {rid}", "Priority": "Must Have", "Source": ""}
        for rid in ("R-01", "R-02", "R-03", "R-04", "123")
    ]
    p["scope"] = [
        _scope("Integration", **{"Req. ID": "r-01"}),  # case-insensitive match
        _scope("SMS connector", SCOPE_OPTIONAL, **{"Req. ID": "R-03"}),
        _scope("Historical migration", SCOPE_OUT, **{"Req. ID": "R-04, 123"}),
    ]
    coverage = {r["ID"]: r["Coverage"] for r in requirement_coverage(p)}
    assert coverage == {
        "R-01": "Covered",
        "R-02": "Not covered",
        "R-03": "Available as add-on",
        "R-04": "Excluded",
        "123": "Excluded",
    }
    warnings = [w for w in validate(p) if "Requirements not addressed" in w]
    assert warnings == ["Requirements not addressed by any scope item: R-02."]


def test_scope_from_requirements_only_drafts_uncovered_ones():
    p = default_proposal()
    p["requirements"] = [
        {"ID": "", "Requirement": "Sync contacts", "Priority": "", "Source": ""},
        {"ID": "", "Requirement": "Renewals pipeline", "Priority": "", "Source": ""},
    ]
    p["scope"] = [_scope("Integration", **{"Req. ID": "R-01"})]
    drafted = scope_from_requirements(p)
    assert [s["Item"] for s in drafted["scope"]] == ["Integration", "Renewals pipeline"]
    assert drafted["scope"][1]["Req. ID"] == "R-02"
    assert all(r["Coverage"] == "Covered" for r in requirement_coverage(drafted))


def test_pricing_summary_separates_one_time_and_recurring_addons():
    p = default_proposal()
    p["milestones"] = [
        {**BLANK_ROWS["milestones"], "Milestone": "M1", "Fee": 11500},
        {**BLANK_ROWS["milestones"], "Milestone": "M2", "Fee": "2,500"},
        {**BLANK_ROWS["milestones"], "Milestone": "", "Fee": 999},  # blank row ignored
    ]
    p["addons"] = [
        {"Service": "Lead scoring", "Includes": "", "Cost": 3500, "Billing": "One Time", "Add to Total": True},
        {"Service": "Support", "Includes": "", "Cost": 500, "Billing": "Monthly", "Add to Total": True},
        {"Service": "SEO", "Includes": "", "Cost": 2500, "Billing": "One Time", "Add to Total": False},
    ]
    p["discount_pct"] = 10
    totals = pricing_summary(p)
    assert totals["milestone_total"] == 14000
    assert totals["selected_addons_one_time"] == 3500
    assert totals["discount"] == 1750
    assert totals["total"] == 15750
    assert totals["recurring"] == {"Monthly": 500}


def test_validate_points_at_missing_exclusions_and_criteria():
    p = default_proposal()
    p["scope"] = [_scope("Workflows")]
    warnings = " ".join(validate(p))
    assert "Out of Scope" in warnings
    assert "acceptance criteria" in warnings
    assert "$0" in warnings


def test_import_from_wrd_fills_blanks_and_appends_rows():
    p = default_proposal()
    p["problem_statement"] = "Already written"
    wrd = {
        "Project Overview": [{"Field": "Purpose", "Value": "Replace spreadsheets"}],
        "Goals": [{"Goal": "One source of truth"}],
        "Customer Requirements": [{"Requirement": "Sync contacts nightly"}, {"Requirement": "Log SMS"}],
        "Project Definitions": [{"Term": "Member", "Definition": "Paying customer"}],
        "Known Challenges or Risks": [{"Type": "Risk", "Description": "Dirty data"}],
        "Project Plan": [{"Milestone": "Go live", "Related Requirement": "1", "Target Date": "2026-12-01 00:00:00", "Status": ""}],
        "Open Questions": [{"Question": "Which ERP?"}],
    }
    merged = import_from_wrd(p, wrd)
    assert merged["problem_statement"] == "Already written"  # never overwritten
    assert [o["Objective"] for o in merged["objectives"]] == ["One source of truth"]
    assert [(r["ID"], r["Requirement"]) for r in merged["requirements"]] == [("R-01", "Sync contacts nightly"), ("R-02", "Log SMS")]
    assert merged["glossary"] == [{"Term": "Member", "Definition": "Paying customer"}]
    assert merged["risks"][0]["Risk"] == "Risk: Dirty data"
    assert merged["timeline"][0]["End"] == "2026-12-01"
    assert merged["assumptions"][-1]["Assumption"] == "To be confirmed: Which ERP?"
    assert p["requirements"][0]["Requirement"] == ""  # input not mutated


def test_import_from_jep_maps_team_needs_and_contact():
    jep = {
        "Solutions Partner Contact": [{"Field": "Contact Name", "Value": "Aylin"}],
        "Team Members": [{"Side": "Prospect", "Role": "Sponsor", "Team Member": "Jane", "Email": "j@acme.com"}],
        "Technical Needs": [{"Functionality": "ERP sync", "Confirmed": "True"}],
        "Business Needs": [{"Functionality": "Forecasting", "Confirmed": "False"}],
        "Milestones": [{"Milestone": "Demo", "Target Date": "2026-10-01"}],
        "Questions": [],
    }
    merged = import_from_jep(default_proposal(), jep, prospect_name="Acme")
    assert merged["client"]["company"] == "Acme"
    assert merged["seller"]["contact"] == "Aylin"
    assert merged["team"] == [{"Side": "Client", "Role": "Sponsor", "Name": "Jane", "Email": "j@acme.com", "Responsibilities": ""}]
    assert [(r["Requirement"], r["Priority"]) for r in merged["requirements"]] == [("ERP sync", "Must Have"), ("Forecasting", "To Confirm")]
    assert merged["timeline"][0]["Phase / Milestone"] == "Demo"


def test_library_items_and_addons_land_in_scope():
    p = add_library_items(default_proposal(), [SCOPE_LIBRARY[0]["Item"]], SCOPE_IN)
    p = add_library_addons(p, [ADDON_LIBRARY[0]["Service"]])
    groups = scope_by_status(p)
    assert groups[SCOPE_IN][0]["Acceptance Criteria"]
    assert groups[SCOPE_OPTIONAL][0]["Item"] == ADDON_LIBRARY[0]["Service"]
    assert p["addons"][0]["Cost"] == ADDON_LIBRARY[0]["Cost"]


def test_json_round_trip_and_template_strips_deal_content():
    p = default_proposal()
    p["client"]["company"] = "Acme"
    p["scope"] = [_scope("Workflows")]
    p["addons"] = [{"Service": "SEO", "Includes": "", "Cost": 1.0, "Billing": "One Time", "Add to Total": True}]
    assert from_json(to_json(p)) == p

    template = as_template(p)
    assert template["client"]["company"] == ""
    assert template["scope"] == default_proposal()["scope"]
    assert template["addons"][0]["Service"] == "SEO"
    assert template["addons"][0]["Add to Total"] is False


def test_from_json_fills_missing_keys_from_defaults():
    loaded = from_json('{"title": "Old file", "client": {"company": "Acme"}}')
    assert loaded["title"] == "Old file"
    assert loaded["client"]["company"] == "Acme"
    assert loaded["client"]["email"] == ""
    assert loaded["methodology"] == default_proposal()["methodology"]


def test_pdf_renders_default_proposal():
    pdf_bytes = proposal_to_pdf(default_proposal())
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_contains_scope_buckets_volumes_and_totals():
    p = default_proposal()
    p["client"]["company"] = "Acme Corp"
    p["title"] = "Sales Hub Implementation"
    p["scope"] = [
        _scope("Build renewals pipeline", **{"Quantity / Limit": "1 pipeline"}),
        _scope("Historical email migration", SCOPE_OUT),
        _scope("Lead Scoring Setup", SCOPE_OPTIONAL),
    ]
    p["addons"] = [{"Service": "Lead Scoring Setup", "Includes": "", "Cost": 3500, "Billing": "One Time", "Add to Total": False}]
    p["milestones"] = [{**BLANK_ROWS["milestones"], "Milestone": "Initial Engagement", "Fee": 11500}]
    p["problem_statement"] = "Deals live in spreadsheets — no visibility."  # non-Latin-1 dash
    text = _pdf_text(proposal_to_pdf(p))
    for expected in (
        "Scope at a Glance", "INCLUDED", "NOT INCLUDED", "AVAILABLE AS ADD-ON",
        "Technical Approach", "Management Approach", "Cost & Pricing",
        "Build renewals pipeline", "Historical email migration", "$3,500.00 One Time", "$11,500.00", "Acme Corp",
    ):
        assert expected in text, expected


def test_pdf_respects_section_toggles():
    p = default_proposal()
    p["sections"]["signatures"] = False
    p["sections"]["rate_card"] = False
    text = _pdf_text(proposal_to_pdf(p))
    assert "Acceptance & Signatures" not in text
    assert "Rate Card" not in text


def test_pdf_has_no_blank_page_after_contents():
    reader = PdfReader(io.BytesIO(proposal_to_pdf(default_proposal())))
    # Every page carries header/footer text; a blank page has nothing else.
    for number, page in enumerate(reader.pages, start=1):
        body = [line for line in page.extract_text().splitlines() if not line.startswith(("SonaMation", "Page ", "Confidential", "Proposal"))]
        assert body, f"page {number} is blank"
