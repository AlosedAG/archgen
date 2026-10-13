"""Discovery build order: the shipped config/discovery_build_order.yaml is
valid, the confirmed scope becomes categorized checkable items with their
source, template items are tagged and listed first, the structured
to_dict() form is JSON-ready, it exports in every section format, and
malformed edits are rejected with messages naming the entry."""

from __future__ import annotations

import json

import pytest

from archscope_domain.discovery import discovery_build_order, discovery_checklist, empty_notes
from archscope_domain.discovery_build_order import (
    COL_DONE,
    COL_ITEM,
    COL_SOURCE,
    COL_STATUS,
    COL_TEMPLATE,
    FROM_SCRATCH,
    SCHEMA_VERSION,
    DiscoveryBuildOrderError,
    parse_build_order_config,
)
from archscope_domain.exporters import sections_to_csv, sections_to_docx, sections_to_pdf, sections_to_xlsx


def _pick(notes, section, qid, *options, other=""):
    notes[section]["answers"][qid] = {"selected": list(options), "other": other, "notes": "", "flagged": False}


def _notes():
    notes = empty_notes()
    _pick(notes, "Data", "data_regions", "EU / UK")
    _pick(notes, "Solutions Design", "integrations", "Salesforce", "Other (specify)", other="Mindbody")
    _pick(notes, "Solutions Design", "priority_features", "Deal pipelines")
    return notes


def test_shipped_config_sections_and_empty_notes():
    config = discovery_build_order()
    order = config.build(empty_notes(), client="Acme")
    assert [s.title for s, _ in order.sections] == [
        "Assets to be created",
        "Segments / Lists",
        "Properties",
        "Pipelines",
        "Record-page updates",
    ]
    assert order.items == []
    assert order.title == f"Acme — {config.project_types[0]} — Build Order"


def test_items_come_from_tasks_scope_and_answers_with_sources():
    order = discovery_build_order().build(_notes(), client="Bright Smiles", project_type="CRM Migration to HubSpot")
    assert order.title == "Bright Smiles — CRM Migration to HubSpot — Build Order"
    by_id = {item.id: item for item in order.items}
    assert by_id["gdpr_form_consent"].sources == ["Required task: Set up GDPR consent / subscription types"]
    assert by_id["integration_setup__salesforce"].name == "Integration: Salesforce"
    assert by_id["integration_setup__salesforce"].sources == ["Scope item: Integration: Salesforce"]
    assert by_id["integration_setup__mindbody"].name == "Integration: Mindbody"
    assert by_id["sales_pipeline"].section == "pipelines"
    assert by_id["sales_pipeline"].sources == ["Priority features (must-haves) → Deal pipelines"]
    assert all(item.status == "Not started" for item in order.items)


def test_template_items_are_tagged_and_listed_first_in_each_section():
    order = discovery_build_order().build(_notes())
    assets = dict((s.key, items) for s, items in order.sections)["assets"]
    flags = [item.is_template for item in assets]
    assert flags == sorted(flags, reverse=True)
    assert True in flags
    assert False in flags
    gdpr = next(item for item in assets if item.id == "gdpr_form_consent")
    assert gdpr.template == "gdpr_bundle"
    assert gdpr.template_label == "GDPR asset bundle"
    rows = dict(order.to_sections())["Assets to be created"]
    assert next(r for r in rows if r[COL_ITEM] == gdpr.name)[COL_TEMPLATE] == "TEMPLATE: GDPR asset bundle"
    assert next(r for r in rows if r[COL_ITEM] == "Integration: Salesforce")[COL_TEMPLATE] == FROM_SCRATCH


def test_done_ids_set_status_and_tick():
    order = discovery_build_order().build(_notes(), done_ids={"gdpr_form_consent"})
    rows = [r for _, rows in order.to_sections() for r in rows]
    assert list(rows[0]) == [COL_DONE, COL_ITEM, COL_SOURCE, COL_TEMPLATE, COL_STATUS]
    done = next(r for r in rows if r[COL_ITEM] == "Consent checkboxes on every form")
    assert (done[COL_DONE], done[COL_STATUS]) == ("[x]", "Done")
    other = next(r for r in rows if r[COL_ITEM] == "Integration: Salesforce")
    assert (other[COL_DONE], other[COL_STATUS]) == ("[ ]", "Not started")


def test_to_dict_is_json_ready_and_structured():
    order = discovery_build_order().build(_notes(), client="Bright Smiles", generated_on="2026-10-12")
    data = json.loads(json.dumps(order.to_dict()))
    assert data["schema"] == SCHEMA_VERSION
    assert data["title"] == order.title
    assert data["generated_on"] == "2026-10-12"
    assert [s["id"] for s in data["sections"]] == ["assets", "segments", "properties", "pipelines", "record_pages"]
    item = next(i for s in data["sections"] for i in s["items"] if i["id"] == "gdpr_form_consent")
    assert item == {
        "id": "gdpr_form_consent",
        "name": "Consent checkboxes on every form",
        "sources": ["Required task: Set up GDPR consent / subscription types"],
        "template": "gdpr_bundle",
        "template_label": "GDPR asset bundle",
        "status": "Not started",
        "done": False,
    }


def test_same_item_from_two_triggers_is_merged_with_both_sources():
    config = parse_build_order_config(
        {
            "project_types": ["Impl"],
            "statuses": ["Open", "Done"],
            "done_status": "Done",
            "sections": [{"id": "assets", "title": "Assets"}],
            "items": [
                {"id": "a", "section": "assets", "name": "Consent forms", "task": "gdpr_consent_setup"},
                {
                    "id": "b",
                    "section": "assets",
                    "name": "Consent forms",
                    "answer": {"question_id": "compliance", "value": "GDPR"},
                },
            ],
        },
        discovery_checklist(),
    )
    notes = empty_notes()
    _pick(notes, "Data", "compliance", "GDPR")
    (item,) = config.build(notes).items
    assert item.id == "a"
    assert item.sources == [
        "Required task: Set up GDPR consent / subscription types",
        "Security / compliance requirements → GDPR",
    ]


def test_build_order_exports_in_every_section_format():
    order = discovery_build_order().build(_notes(), client="Bright Smiles")
    sections = order.to_sections()
    assert "Integration: Salesforce" in sections_to_csv(sections)
    assert sections_to_pdf(order.title, "", sections).startswith(b"%PDF")
    assert sections_to_xlsx(sections)[:2] == b"PK"
    assert sections_to_docx(order.title, "", sections).getvalue()[:2] == b"PK"


BASE = {
    "project_types": ["Impl"],
    "statuses": ["Open", "Done"],
    "done_status": "Done",
    "sections": [{"id": "assets", "title": "Assets"}],
    "templates": {"gdpr_bundle": "GDPR"},
}


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"id": "x", "section": "nope", "name": "n", "task": "gdpr_consent_setup"}, "'section' must be one of"),
        ({"id": "x", "section": "assets", "name": "n", "template": "nope", "task": "gdpr_consent_setup"}, "unknown template"),
        ({"id": "x", "section": "assets", "name": "n"}, "exactly one trigger"),
        (
            {"id": "x", "section": "assets", "name": "n", "task": "gdpr_consent_setup", "scope": "integrations"},
            "exactly one trigger",
        ),
        ({"id": "x", "section": "assets", "name": "n", "task": "typo"}, "isn't a task in discovery_rules.yaml"),
        (
            {"id": "x", "section": "assets", "name": "n", "scope": "compliance"},
            "isn't a question listed in discovery_checklist.yaml",
        ),
        ({"id": "x", "section": "assets", "name": "{option}", "task": "gdpr_consent_setup"}, "only works with a 'scope' trigger"),
        (
            {"id": "x", "section": "assets", "name": "n", "answer": {"question_id": "compliance", "value": "gdpr"}},
            "isn't an option of",
        ),
        (
            {"id": "x", "section": "assets", "name": "n", "answer": {"question_id": "long_term_goals", "value": "a"}},
            "choice question_id",
        ),
        ({"id": "Bad Id", "section": "assets", "name": "n", "task": "gdpr_consent_setup"}, "snake_case"),
    ],
)
def test_invalid_items_are_reported(item, expected):
    with pytest.raises(DiscoveryBuildOrderError) as exc:
        parse_build_order_config({**BASE, "items": [item]}, discovery_checklist())
    assert any(expected in p for p in exc.value.problems), exc.value.problems


def test_invalid_top_level_settings_are_reported_together():
    raw = {**BASE, "statuses": [], "done_status": "Done", "sections": [{"id": "a", "title": ""}], "items": []}
    with pytest.raises(DiscoveryBuildOrderError) as exc:
        parse_build_order_config(raw, discovery_checklist())
    assert any("'statuses' must be" in p for p in exc.value.problems)
    assert any("'title' is required" in p for p in exc.value.problems)
