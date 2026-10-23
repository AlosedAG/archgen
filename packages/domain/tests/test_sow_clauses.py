"""The SOW's clause library: tokens filled from the SOW, [[blanks]] that hold
up sending only while their clause is switched on, and the PDF's terms."""

from __future__ import annotations

import io

from pypdf import PdfReader

from archscope_domain import proposal as dp
from archscope_domain import sow_clauses as sc
from archscope_domain.proposal_pdf import proposal_to_pdf


def test_the_standard_set_covers_the_agreed_terms() -> None:
    keys = [k for k, *_ in sc.DEFAULT_CLAUSES]
    for key in (
        "ip_ownership",
        "warranty",
        "liability",
        "termination",
        "governing_law",
        "data_protection",
        "force_majeure",
        "non_solicitation",
        "entire_agreement",
        "msa_reference",
        "validity",
    ):
        assert key in keys
    assert len(set(keys)) == len(keys)
    off = [k for k, _, _, on in sc.DEFAULT_CLAUSES if not on]
    assert off == ["msa_reference"]  # optional: only for clients with an MSA
    liability = next(b for k, _, b, _ in sc.DEFAULT_CLAUSES if k == "liability")
    assert "[[liability cap" in liability


def test_tokens_fill_from_the_sow_and_missing_ones_become_blanks() -> None:
    p = dp.default_proposal()
    p["client"]["company"] = "Acme"
    body = "{{client}} and {{seller}} agree; valid until {{valid_until}}; {{unknown}} stays."
    assert sc.render_clause(p, body) == "Acme and SonaMation agree; valid until [[proposal validity date]]; {{unknown}} stays."
    p["valid_until"] = "2026-12-31"
    assert "valid until 2026-12-31" in sc.render_clause(p, body)


def test_only_switched_on_clauses_hold_up_sending() -> None:
    p = dp.default_proposal()
    p["client"]["company"] = "Acme"
    p["payment_schedule"] = {**p["payment_schedule"], "invoicing": "Monthly in arrears", "due_terms": "Net 30"}
    p["tier_assumption"] = "Sales Hub Professional."
    issues = dp.readiness_issues(p)
    assert any(i.startswith("Terms - Limitation of Liability: fill in [[liability cap") for i in issues)
    assert not any(i.startswith("Terms - Master Services Agreement") for i in issues)  # switched off by default

    for c in p["clauses"]:
        c["Include"] = c["Key"] == "liability"
    liability = next(c for c in p["clauses"] if c["Key"] == "liability")
    liability["Body"] = "Liability is capped at the fees paid in the 12 months before the claim."
    assert dp.readiness_issues(p) == []


def test_missing_library_clauses_are_added_once() -> None:
    sow = [{"Key": "warranty", "Title": "My warranty", "Body": "Edited.", "Include": True}]
    library = sc.default_clauses()
    merged = sc.add_missing_clauses(sow, library)
    assert merged[0]["Title"] == "My warranty"  # the SOW's own edits are kept
    assert len(merged) == len(library)
    assert sc.add_missing_clauses(merged, library) == merged


def test_pdf_prints_the_switched_on_clauses_with_tokens_filled() -> None:
    p = dp.default_proposal()
    p["client"]["company"] = "Acme"
    p["valid_until"] = "2026-12-31"
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(proposal_to_pdf(p))).pages)
    assert "Limitation of Liability" in text
    assert "Proposal Validity & Effective Date" in text
    assert "valid until 2026-12-31" in text
    assert "is issued under, and governed by" not in text  # the MSA clause is off by default
    assert "{{client}}" not in text
