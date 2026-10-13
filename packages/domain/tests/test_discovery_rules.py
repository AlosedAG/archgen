"""Discovery "gotcha" rules: the shipped config/discovery_rules.yaml is
valid and fires the reference rules, chained rules work, malformed edits
are rejected with messages naming the entry, and revealed follow-ups and
required tasks reach the business-analysis payload."""

from __future__ import annotations

import pytest

from archscope_domain.discovery import (
    FOLLOW_UP_LABEL_PREFIX,
    REQUIRED_TASKS_PREFIX,
    build_business_analysis_input,
    discovery_rules,
    empty_notes,
)
from archscope_domain.discovery_config import parse_question_bank
from archscope_domain.discovery_rules import DiscoveryRulesError, parse_discovery_rules


def _pick(notes, section, qid, *options, flagged=False):
    notes[section]["answers"][qid] = {"selected": list(options), "other": "", "notes": "", "flagged": flagged}


def test_shipped_rules_are_valid():
    rules = discovery_rules()
    assert rules.rules
    assert set(rules.home_sections) == set(rules.follow_ups)


def test_no_answers_reveal_nothing():
    evaluation = discovery_rules().evaluate(empty_notes())
    assert evaluation.follow_ups == {}
    assert evaluation.tasks == []


def test_eu_uk_contacts_reveal_gdpr_follow_ups_and_tasks():
    notes = empty_notes()
    _pick(notes, "Data", "data_regions", "United States", "EU / UK")
    evaluation = discovery_rules().evaluate(notes)
    assert [q.key for q in evaluation.follow_ups["data_regions"]] == [
        "gdpr_lawful_basis",
        "gdpr_consent_capture",
        "data_residency",
    ]
    labels = [t.task.label for t in evaluation.tasks]
    assert "Set up GDPR consent / subscription types" in labels
    assert "Configure data residency considerations" in labels
    assert all(t.section == "Data" for t in evaluation.tasks)
    assert evaluation.tasks[0].reasons == ("Where are their customers / contacts located? → EU / UK",)


def test_multiple_locations_reveal_ownership_and_routing():
    for option in ["Multiple locations (same country)", "Multi-region / international", "Franchise model"]:
        notes = empty_notes()
        _pick(notes, "Data", "org_structure", option)
        evaluation = discovery_rules().evaluate(notes)
        revealed = evaluation.revealed_ids
        assert {"location_ownership", "location_routing"} <= revealed, option
        assert "Build lead and ticket routing per location / region" in [t.task.label for t in evaluation.tasks]
    notes = empty_notes()
    _pick(notes, "Data", "org_structure", "Single location")
    assert not discovery_rules().evaluate(notes).revealed_ids


def test_tasks_flagged_by_several_rules_appear_once_with_every_reason():
    notes = empty_notes()
    _pick(notes, "Data", "data_regions", "EU / UK")
    _pick(notes, "Data", "compliance", "GDPR")
    evaluation = discovery_rules().evaluate(notes)
    keys = [t.task.key for t in evaluation.tasks]
    assert len(keys) == len(set(keys))
    consent = next(t for t in evaluation.tasks if t.task.key == "gdpr_consent_setup")
    assert len(consent.reasons) == 2
    # Revealed once, under the first question that revealed it.
    assert "gdpr_lawful_basis" not in [q.key for q in evaluation.follow_ups.get("compliance", [])]


def test_chained_rule_fires_only_while_its_follow_up_is_showing():
    notes = empty_notes()
    _pick(notes, "Data", "region_differences", "Multiple currencies")
    # The follow-up was answered but isn't showing — its rule doesn't fire.
    assert "multi_currency" not in [t.task.key for t in discovery_rules().evaluate(notes).tasks]
    _pick(notes, "Data", "org_structure", "Multi-region / international")
    evaluation = discovery_rules().evaluate(notes)
    assert "region_differences" in [q.key for q in evaluation.follow_ups["org_structure"]]
    assert "multi_currency" in [t.task.key for t in evaluation.tasks]


def test_payload_includes_revealed_follow_ups_and_required_tasks():
    notes = empty_notes()
    _pick(notes, "Data", "data_regions", "EU / UK")
    _pick(notes, "Data", "gdpr_lawful_basis", "Consent (opt-in)", flagged=True)
    # Answered earlier, then hidden when org_structure changed: left out.
    _pick(notes, "Data", "location_ownership", "Not defined yet")
    data = build_business_analysis_input(notes)["sections"]["Data"]
    labels = list(data["answers"])
    trigger = labels.index("Where are their customers / contacts located?")
    lawful_basis = FOLLOW_UP_LABEL_PREFIX + "GDPR — lawful basis for processing EU / UK contacts' data"
    assert labels[trigger + 1] == lawful_basis
    assert data["answers"][lawful_basis] == "Consent (opt-in)"
    # Revealed but blank: still sent, so it becomes a gap.
    assert data["answers"][FOLLOW_UP_LABEL_PREFIX + "Must EU / UK data be hosted in the EU?"] == ""
    assert not any("own records" in label for label in labels)
    assert lawful_basis in data["edge_cases"]
    assert REQUIRED_TASKS_PREFIX + "Set up GDPR consent / subscription types" in data["edge_cases"]
    goals = build_business_analysis_input(notes)["sections"]["Goals"]
    assert REQUIRED_TASKS_PREFIX not in goals["edge_cases"]


# ---- Validation -------------------------------------------------------------

BANK = parse_question_bank(
    {
        "sections": {
            "Data": [
                {"id": "regions", "label": "Regions", "input": "multiselect", "options": ["EU / UK", "US"]},
                {"id": "why", "label": "Why?"},
            ]
        }
    }
)
FOLLOW_UP = {"gdpr": {"label": "GDPR basis?", "input": "select", "options": ["Consent"]}}
TASKS = {"consent": {"label": "Set up consent"}}


def _rules(rules, follow_ups=FOLLOW_UP, tasks=TASKS):
    return parse_discovery_rules({"follow_ups": follow_ups, "tasks": tasks, "rules": rules}, BANK)


def test_minimal_rule_parses_and_accepts_shorthand():
    rules = parse_discovery_rules(
        {
            "follow_ups": FOLLOW_UP,
            "tasks": {"consent": "Set up consent"},
            "rules": [{"trigger": {"question_id": "regions", "value": "EU / UK"}, "reveals": "gdpr", "flags": ["consent"]}],
        },
        BANK,
    )
    assert rules.rules[0].values == ("EU / UK",)
    assert rules.rules[0].reveals == ("gdpr",)
    assert rules.tasks["consent"].label == "Set up consent"
    assert rules.home_sections == {"gdpr": "Data"}


def test_empty_file_means_no_rules():
    assert parse_discovery_rules(None, BANK).rules == []


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ({"trigger": {"question_id": "nope", "value": "x"}, "flags": ["consent"]}, "isn't a question or follow-up id"),
        ({"trigger": {"question_id": "why", "value": "x"}, "flags": ["consent"]}, "is a text question"),
        ({"trigger": {"question_id": "regions", "value": "EU/UK"}, "flags": ["consent"]}, "isn't an option of 'regions'"),
        ({"trigger": {"question_id": "regions", "value": True}, "flags": ["consent"]}, "quote Yes/No"),
        ({"trigger": {"question_id": "regions", "value": []}, "flags": ["consent"]}, "trigger 'value'"),
        ({"trigger": {"question_id": "regions", "value": "US"}}, "needs 'reveals' and/or 'flags'"),
        ({"trigger": {"question_id": "regions", "value": "US"}, "flags": ["typo"]}, "unknown follow-up / task id(s) typo"),
        ({"reveals": ["gdpr"]}, "needs a 'trigger:'"),
    ],
)
def test_invalid_rules_are_reported(rule, expected):
    with pytest.raises(DiscoveryRulesError) as exc:
        _rules([{"trigger": {"question_id": "regions", "value": "EU / UK"}, "reveals": ["gdpr"]}, rule])
    assert any(expected in p for p in exc.value.problems), exc.value.problems


def test_follow_up_ids_cannot_reuse_question_ids_and_must_be_reachable():
    with pytest.raises(DiscoveryRulesError) as exc:
        _rules(
            [{"trigger": {"question_id": "loop_a", "value": "Yes"}, "reveals": ["loop_b"]}],
            follow_ups={
                "regions": {"label": "dup"},
                "loop_a": {"label": "A", "input": "radio", "options": ["Yes"]},
                "loop_b": {"label": "B", "input": "radio", "options": ["Yes"]},
            },
        )
    problems = exc.value.problems
    assert any("follow_ups › regions" in p and "already a question" in p for p in problems)
    assert any("follow_ups › loop_a: never shown" in p for p in problems)
    assert any("follow_ups › loop_b: never shown" in p for p in problems)


def test_rules_referencing_an_invalid_follow_up_report_only_the_follow_up():
    with pytest.raises(DiscoveryRulesError) as exc:
        _rules(
            [{"trigger": {"question_id": "regions", "value": "US"}, "reveals": ["gdpr"]}],
            follow_ups={"gdpr": {"label": "GDPR?", "input": "select"}},
        )
    assert exc.value.problems == ["follow_ups › gdpr: a 'select' question needs 'options'"]


def test_evaluation_records_which_options_revealed_each_follow_up():
    notes = empty_notes()
    _pick(notes, "Data", "data_regions", "United States", "EU / UK")
    _pick(notes, "Data", "org_structure", "Franchise model")
    revealed_by = discovery_rules().evaluate(notes).revealed_by
    assert revealed_by["gdpr_lawful_basis"] == ("EU / UK",)
    assert revealed_by["location_routing"] == ("Franchise model",)
