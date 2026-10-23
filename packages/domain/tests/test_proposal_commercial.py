"""Commercial completeness for the SOW: workstream pricing, recurring fees,
the week-based timeline, migration projects, the "Ready to send" gate and
the sections drafted from earlier steps."""

from __future__ import annotations

import io

from pypdf import PdfReader

from archscope_domain import proposal as dp
from archscope_domain.proposal_pdf import proposal_to_pdf


def _ready_doc() -> dict:
    p = dp.default_proposal()
    p["client"]["company"] = "Acme"
    p["tier_assumption"] = "Designed for Sales Hub Professional."
    p["payment_schedule"] = {**p["payment_schedule"], "invoicing": "Per milestone, on acceptance", "due_terms": "Net 30"}
    p["clauses"] = [{**c, "Include": False} for c in p["clauses"]]  # the terms' blanks are tested in test_sow_clauses
    return p


def test_milestone_fees_group_by_workstream_with_fee_basis() -> None:
    p = dp.default_proposal()
    p["milestones"] = [
        {
            **dp.BLANK_ROWS["milestones"],
            "Milestone": "M1",
            "Workstream / Phase": "Discovery",
            "Fee": 3000,
            "Fee Basis": "Fixed fee",
        },
        {**dp.BLANK_ROWS["milestones"], "Milestone": "M2", "Workstream / Phase": "Build", "Fee": 8000},
        {
            **dp.BLANK_ROWS["milestones"],
            "Milestone": "M3",
            "Workstream / Phase": "Discovery",
            "Fee": 1000,
            "Fee Basis": "Workshops",
        },
        {**dp.BLANK_ROWS["milestones"], "Milestone": "M4", "Fee": 500},
    ]
    groups = dp.pricing_summary(p)["workstreams"]
    assert [(g["workstream"], g["fee"], g["fee_basis"], g["milestones"]) for g in groups] == [
        ("Discovery", 4000.0, "Fixed fee; Workshops", ["M1", "M3"]),
        ("Build", 8000.0, "", ["M2"]),
        ("General", 500.0, "", ["M4"]),
    ]


def test_recurring_fees_total_apart_from_one_time() -> None:
    p = dp.default_proposal()
    p["milestones"] = [{**dp.BLANK_ROWS["milestones"], "Milestone": "M1", "Fee": 10000}]
    p["recurring_fees"] = [
        {
            **dp.BLANK_ROWS["recurring_fees"],
            "Service": "Support retainer",
            "Amount": 500,
            "Cadence": "Monthly",
            "Term (Months)": 12,
        },
        {
            **dp.BLANK_ROWS["recurring_fees"],
            "Service": "Quarterly review",
            "Amount": 1500,
            "Cadence": "Quarterly",
            "Term (Months)": 12,
        },
    ]
    p["addons"] = [{"Service": "Chat support", "Includes": "", "Cost": 100, "Billing": "Monthly", "Add to Total": True}]
    totals = dp.pricing_summary(p)
    assert totals["total"] == 10000  # one-time only
    assert totals["recurring"] == {"Monthly": 600.0, "Quarterly": 1500.0}
    assert totals["recurring_term_total"] == 500 * 12 + 1500 * 4


def test_timeline_chart_sequences_overlaps_and_adds_the_buffer() -> None:
    p = dp.default_proposal()
    row = dp.BLANK_ROWS["timeline"]
    p["timeline"] = [
        {**row, "Phase / Milestone": "Discovery", "Duration (Weeks)": 2},  # starts week 1
        {**row, "Phase / Milestone": "Design", "Duration (Weeks)": 3},  # follows: weeks 3-5
        {**row, "Phase / Milestone": "Build", "Start Week": 4, "Duration (Weeks)": 4},  # overlaps Design: weeks 4-7
        {**row, "Phase / Milestone": "Go-live", "Duration (Weeks)": 0},  # not charted
    ]
    p["timeline_buffer_weeks"] = 2
    chart = dp.timeline_chart(p)
    assert [(b["Phase"], b["Start"], b["Weeks"], b["Buffer"]) for b in chart["bars"]] == [
        ("Discovery", 1.0, 2.0, False),
        ("Design", 3.0, 3.0, False),
        ("Build", 4.0, 4.0, False),
        ("Validation & buffer", 8.0, 2.0, True),
    ]
    assert chart["total_weeks"] == 9


def test_migration_follows_the_scope_unless_set_by_hand() -> None:
    p = dp.add_library_items(dp.default_proposal(), ["Data import / migration"])
    assert dp.migration_scope_items(p)
    assert dp.is_migration(p)
    p["is_migration"] = False
    assert not dp.is_migration(p)
    q = dp.default_proposal()
    assert not dp.is_migration(q)
    q["is_migration"] = True
    assert dp.is_migration(q)


def test_ready_to_send_gate() -> None:
    fresh = dp.default_proposal()
    issues = dp.readiness_issues(fresh)
    assert any(i.startswith("Payment schedule") for i in issues)
    assert any("Subscription-tier assumption" in i and "[[" in i for i in issues)  # the shipped blank

    ready = _ready_doc()
    assert dp.readiness_issues(ready) == []

    ready["is_migration"] = True
    assert any("data migration" in i for i in dp.readiness_issues(ready))
    ready["data_quality"] = [{"Issue": "Duplicate contacts", "Risk if Not Resolved": "Double emails", "Owner": "Client"}]
    assert dp.readiness_issues(ready) == []

    ready["exec_key_risks"] = "Depends on [[client data owner]]."
    assert dp.readiness_issues(ready) == ["Executive summary (key risks): fill in [[client data owner]]."]
    ready["sections"]["executive_summary"] = False  # a switched-off section's blanks don't count
    assert dp.readiness_issues(ready) == []

    ready["status"] = dp.STATUS_READY
    assert dp.is_ready(ready)


def test_prefill_from_earlier_steps() -> None:
    p = dp.default_proposal()
    p["scope"] = [{**dp.BLANK_ROWS["scope"], "Item": "Provide CRM export", "Status": dp.SCOPE_CLIENT}]
    p = dp.responsibilities_from_scope(p)
    assert {"Responsibility": "Provide CRM export"} in p["client_responsibilities"]
    assert len(dp.responsibilities_from_scope(p)["client_responsibilities"]) == len(p["client_responsibilities"])  # no repeat

    p = dp.timeline_from_methodology(p)
    phases = [r for r in p["timeline"] if r.get("Duration (Weeks)")]
    assert phases[0]["Phase / Milestone"] == "Discovery & Requirements"
    assert [r["Start Week"] for r in phases] == [1.0, 3.0, 5.0, 9.0, 11.0]
    p["timeline"][0]["Duration (Weeks)"] = 6
    assert dp.timeline_from_methodology(p)["timeline"] == p["timeline"]  # a planned schedule is left alone

    findings = [
        {"severity": "Low", "description": "Unused list"},
        {"severity": "Medium", "description": "Two 'Lead Source' properties"},
        {"severity": "High", "description": "Contacts without email"},
    ]
    p = dp.data_quality_from_findings(p, findings)
    issues = [r["Issue"] for r in dp.nonblank(p["data_quality"], "Issue")]
    assert issues == ["Contacts without email", "Two 'Lead Source' properties"]


def test_old_documents_load_with_the_new_fields() -> None:
    old = {"title": "Old", "payment_schedule": {"due_terms": "Net 15"}}
    p = dp.from_json(dp.to_json(old))
    assert p["payment_schedule"]["due_terms"] == "Net 15"
    assert p["payment_schedule"]["deposit_type"] == "Percent"
    assert p["vendor_responsibilities"]
    assert p["timeline_buffer_weeks"] == 2.0


def test_pdf_has_the_new_sections_and_marks_drafts() -> None:
    p = _ready_doc()
    p["executive_summary"] = "We rebuild the CRM."
    p["exec_key_risks"] = "Data quality."
    p["milestones"] = [
        {
            **dp.BLANK_ROWS["milestones"],
            "Milestone": "M1",
            "Workstream / Phase": "Discovery",
            "Fee": 3000,
            "Fee Basis": "Fixed fee",
            "Acceptance Evidence": "Signed WRD",
        }
    ]
    p["recurring_fees"] = [{**dp.BLANK_ROWS["recurring_fees"], "Service": "Support retainer", "Amount": 500}]
    p["timeline"] = [{**dp.BLANK_ROWS["timeline"], "Phase / Milestone": "Discovery", "Duration (Weeks)": 2}]
    p["data_quality"] = [{"Issue": "Duplicate contacts", "Risk if Not Resolved": "Double emails", "Owner": "Client"}]

    def text(doc: dict) -> str:
        return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(proposal_to_pdf(doc))).pages)

    draft = text(p)
    for expected in (
        "At a Glance",
        "Total investment",
        "Responsibilities",
        "Indicative Timeline",
        "Validation & buffer",
        "Milestone Acceptance Evidence",
        "Signed WRD",
        "Data Quality & Known Issues",
        "Recurring Fees",
        "Total one-time fee",
        "Payment Schedule",
        "Net 30",
        "Subscription tier",
        "DRAFT",
    ):
        assert expected in draft, expected
    p["status"] = dp.STATUS_READY
    assert "DRAFT" not in text(p)
