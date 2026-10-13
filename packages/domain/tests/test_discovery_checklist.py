"""Discovery required-tasks checklist: the shipped
config/discovery_checklist.yaml is valid, required tasks and scope items
become rows with the answer that triggered them and a blank status column,
the result exports in every section format, and malformed edits are
rejected with messages naming the entry."""

from __future__ import annotations

import pytest

from archscope_domain.discovery import discovery_checklist, discovery_rules, empty_notes
from archscope_domain.discovery_checklist import (
    COL_STATUS,
    COL_TASK,
    COL_WHY,
    REQUIRED_TASKS_TITLE,
    SCOPE_ITEMS_TITLE,
    DiscoveryChecklistError,
    parse_checklist_config,
)
from archscope_domain.exporters import sections_to_csv, sections_to_docx, sections_to_pdf, sections_to_xlsx


def _pick(notes, section, qid, *options, other=""):
    notes[section]["answers"][qid] = {"selected": list(options), "other": other, "notes": "", "flagged": False}


def test_empty_notes_give_an_empty_checklist():
    assert discovery_checklist().build(empty_notes()) == [(REQUIRED_TASKS_TITLE, []), (SCOPE_ITEMS_TITLE, [])]


def test_required_tasks_carry_task_reason_and_blank_status():
    notes = empty_notes()
    _pick(notes, "Data", "data_regions", "EU / UK")
    _pick(notes, "Data", "compliance", "GDPR")
    tasks = dict(discovery_checklist().build(notes))[REQUIRED_TASKS_TITLE]
    consent = next(r for r in tasks if r[COL_TASK].startswith("Set up GDPR consent / subscription types"))
    assert list(consent) == [COL_TASK, COL_WHY, COL_STATUS]
    assert consent[COL_TASK] == (
        "Set up GDPR consent / subscription types — Turn on GDPR tools, define subscription types, "
        "and add consent checkboxes to every form"
    )
    assert consent[COL_WHY] == (
        "Where are their customers / contacts located? → EU / UK; Security / compliance requirements → GDPR"
    )
    assert consent[COL_STATUS] == ""
    assert len(tasks) == len(discovery_rules().evaluate(notes).tasks)


def test_scope_items_from_picked_options_skip_excluded_and_use_other_text():
    notes = empty_notes()
    _pick(notes, "Solutions Design", "integrations", "Salesforce", "Other (specify)", other="Mindbody")
    _pick(notes, "Data", "custom_data", "None identified")
    _pick(notes, "Solutions Design", "priority_features", "Quotes", "Other (specify)")  # Other left blank
    scope = dict(discovery_checklist().build(notes))[SCOPE_ITEMS_TITLE]
    assert [r[COL_TASK] for r in scope] == ["Must-have feature: Quotes", "Integration: Salesforce", "Integration: Mindbody"]
    assert scope[2][COL_WHY] == "Integrations needed → Other: Mindbody"
    assert all(r[COL_STATUS] == "" for r in scope)


def test_checklist_exports_in_every_section_format():
    notes = empty_notes()
    _pick(notes, "Data", "org_structure", "Franchise model")
    _pick(notes, "Solutions Design", "integrations", "Slack")
    checklist = discovery_checklist().build(notes)
    assert "Integration: Slack" in sections_to_csv(checklist)
    assert sections_to_pdf("Checklist", "", checklist).startswith(b"%PDF")
    assert sections_to_xlsx(checklist)[:2] == b"PK"
    assert sections_to_docx("Checklist", "", checklist).getvalue()[:2] == b"PK"


def test_follow_up_scope_source_counts_only_while_showing():
    config = parse_checklist_config({"scope_items": [{"question_id": "location_routing"}]}, discovery_rules())
    notes = empty_notes()
    _pick(notes, "Data", "location_routing", "Manual assignment")
    assert dict(config.build(notes))[SCOPE_ITEMS_TITLE] == []
    _pick(notes, "Data", "org_structure", "Multiple locations (same country)")
    scope = dict(config.build(notes))[SCOPE_ITEMS_TITLE]
    assert scope[0][COL_TASK] == "How should leads and tickets route between locations / regions?: Manual assignment"


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"question_id": "nope"}, "isn't a question or follow-up id"),
        ({"question_id": "long_term_goals"}, "is a text question"),
        ({"question_id": "custom_data", "exclude": ["None"]}, "'None' isn't an option of 'custom_data'"),
        ({"question_id": "custom_data", "exclude": [True]}, "'exclude' must be a list"),
        ({"question_id": "integrations", "name": 3}, "'name' must be text"),
        ("integrations", "must be a mapping"),
    ],
)
def test_invalid_entries_are_reported(entry, expected):
    with pytest.raises(DiscoveryChecklistError) as exc:
        parse_checklist_config({"scope_items": [entry]}, discovery_rules())
    assert any(expected in p for p in exc.value.problems), exc.value.problems


def test_duplicate_question_is_reported():
    with pytest.raises(DiscoveryChecklistError) as exc:
        parse_checklist_config({"scope_items": [{"question_id": "integrations"}] * 2}, discovery_rules())
    assert any("listed more than once" in p for p in exc.value.problems)
