"""Industry templates: valid against the question bank, and fill blanks only."""

from __future__ import annotations

import pytest

from archscope_domain import industry_templates as it
from archscope_domain.discovery import question_bank
from archscope_domain.proposal import SCOPE_STATUSES, default_proposal


@pytest.mark.parametrize("industry", [c.id for c in it.industries()])
@pytest.mark.parametrize("size", [None, *(c.id for c in it.sizes())])
def test_every_preset_matches_the_question_bank(industry: str, size: str | None) -> None:
    bank = question_bank()
    questions = {(section, q.key): q for section, qs in bank.sections.items() for q in qs}
    for section, answers in it.discovery_answers(industry, size).items():
        for question, value in answers.items():
            q = questions.get((section, question))
            assert q is not None, f"{industry}: {section} › {question} isn't in the question bank"
            assert q.input != "text", f"{question} is a text question"
            values = value if isinstance(value, list) else [value]
            assert isinstance(value, list) == (q.input == "multiselect"), f"{question}: list only for multiselect"
            for v in values:
                assert v in q.options, f"{industry}/{size}: '{v}' isn't an option of {question}"


@pytest.mark.parametrize("industry", [c.id for c in it.industries()])
def test_proposal_rows_use_known_statuses(industry: str) -> None:
    for row in it.proposal_rows(industry, "enterprise").get("scope", []):
        assert row["status"] in SCOPE_STATUSES
        assert row["item"]


def test_apply_discovery_keeps_captured_answers() -> None:
    notes = {
        "Goals": {
            "answers": {"growth_areas": {"selected": ["Brand awareness"], "other": "", "notes": "", "flagged": False}},
            "notes": "",
            "edge_cases": "",
        }
    }
    filled_notes, business_type, filled = it.apply_discovery(notes, "", "saas", "smb")
    assert filled_notes["Goals"]["answers"]["growth_areas"]["selected"] == ["Brand awareness"]  # not replaced
    assert filled_notes["Goals"]["answers"]["timeline"]["selected"] == ["1–3 months"]  # from the size
    assert business_type == "B2B software / SaaS company"
    assert filled > 10
    assert notes["Goals"]["answers"].keys() == {"growth_areas"}  # input not mutated

    _, kept_type, _ = it.apply_discovery({}, "Typed type", "saas")
    assert kept_type == "Typed type"


def test_size_lists_combine_with_the_industry() -> None:
    compliance = it.discovery_answers("saas", "enterprise")["Data"]["compliance"]
    assert compliance == ["GDPR", "SOC 2", "Data residency requirements"]


def test_apply_proposal_twice_adds_nothing_the_second_time() -> None:
    once, changed = it.apply_proposal(default_proposal(), "healthcare", "mid_market")
    assert {"objectives", "scope", "assumptions", "risks", "kpis", "glossary"} <= set(changed)
    twice, changed_again = it.apply_proposal(once, "healthcare", "mid_market")
    assert changed_again == []
    assert twice["scope"] == once["scope"]


def test_unknown_template_is_an_error() -> None:
    with pytest.raises(it.TemplateError):
        it.discovery_answers("aerospace")
    with pytest.raises(it.TemplateError):
        it.proposal_rows("saas", "huge")
