"""Discovery Call Assistant: payload building, the Claude request shape,
streaming/stop-reason handling (against a fake client — no network), and
mapping the business analysis's recommended hubs to the explainer."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.discovery import (
    FALLBACK_BETA,
    HUBSPOT_MODULES,
    MODE_BUSINESS_ANALYSIS,
    MODE_CLIENT_EXPLAINER,
    SYSTEM_PROMPT,
    DiscoveryError,
    build_business_analysis_input,
    build_client_explainer_input,
    build_request,
    empty_notes,
    format_answer,
    has_any_notes,
    sections,
    stream_document,
    suggest_modules,
)


def test_empty_notes_have_no_content():
    assert not has_any_notes(empty_notes())


def test_edge_case_alone_counts_as_notes():
    notes = empty_notes()
    notes["Data"]["edge_cases"] = "HIPAA"
    assert has_any_notes(notes)


def test_business_analysis_payload_keeps_blank_answers_and_uses_question_labels():
    notes = empty_notes()
    # A plain string (notes from before answers were structured) still works.
    notes["Goals"]["answers"]["kpis"] = "  lead-to-patient rate  "
    payload = build_business_analysis_input(notes, client_name="Bright Smiles", business_type="dental")

    assert payload["mode"] == MODE_BUSINESS_ANALYSIS
    assert payload["client"] == {"name": "Bright Smiles", "business_type": "dental"}
    assert list(payload["sections"]) == list(sections())
    goals = payload["sections"]["Goals"]["answers"]
    assert goals["KPIs — how will they measure success?"] == "lead-to-patient rate"
    # Blank answers are sent as "" (they become follow-up gaps), not dropped.
    assert len(goals) == len(sections()["Goals"])
    assert goals["Timeline / key dates"] == ""


def test_structured_answers_are_flattened_for_the_model():
    notes = empty_notes()
    notes["Data"]["answers"]["compliance"] = {
        "selected": ["HIPAA", "Other (specify)"],
        "other": "state privacy law",
        "notes": "legal reviewing",
        "flagged": False,
    }
    notes["Data"]["answers"]["sync_direction"] = {"selected": ["Two-way sync"], "other": "", "notes": "", "flagged": False}
    answers = build_business_analysis_input(notes)["sections"]["Data"]["answers"]
    assert answers["Security / compliance requirements"] == "HIPAA; Other: state privacy law — notes: legal reviewing"
    assert answers["Sync direction(s) needed"] == "Two-way sync"


def test_format_answer_variants():
    assert format_answer(None) == ""
    assert format_answer({"selected": [], "other": "", "notes": "", "flagged": True}) == ""
    assert format_answer({"selected": [], "notes": "only notes"}) == "only notes"
    assert format_answer({"selected": ["Other (specify)"]}) == "Other (not specified)"
    # "Other" text is ignored unless the Other option is actually picked.
    assert format_answer({"selected": ["Email"], "other": "stale"}) == "Email"
    # A single select's value may arrive as a bare string.
    assert format_answer({"selected": "Weekly"}) == "Weekly"


def test_flagged_questions_go_to_edge_cases_and_count_as_unanswered():
    notes = empty_notes()
    notes["Data"]["edge_cases"] = "Two legal entities"
    notes["Data"]["answers"]["volume"]["flagged"] = True
    notes["Data"]["answers"]["compliance"]["flagged"] = True
    data = build_business_analysis_input(notes)["sections"]["Data"]
    assert data["edge_cases"] == (
        "Two legal entities\nSpecialist flagged for follow-up (confirm before scoping): "
        "Volume — objects, records, assets; Security / compliance requirements"
    )
    assert data["answers"]["Volume — objects, records, assets"] == ""
    assert build_business_analysis_input(empty_notes())["sections"]["Data"]["edge_cases"] == ""


def test_client_explainer_payload_omits_blank_business_type():
    assert build_client_explainer_input(["Sales Hub"]) == {"mode": MODE_CLIENT_EXPLAINER, "modules": ["Sales Hub"]}
    assert build_client_explainer_input(["Sales Hub"], business_type="gym")["business_type"] == "gym"


def test_request_uses_verbatim_cached_system_prompt_and_fallbacks():
    payload = build_client_explainer_input(["Sales Hub"])
    request = build_request(payload, model="claude-opus-5-5")
    assert request["model"] == "claude-opus-5-5"
    assert request["system"][0]["text"] == SYSTEM_PROMPT
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert FALLBACK_BETA in request["betas"]
    assert request["extra_body"] == {"fallbacks": "default"}
    content = request["messages"][0]["content"]
    payload_json, format_note = content.split("\n\n", 1)
    assert json.loads(payload_json) == payload
    assert "Markdown" in format_note


class _FakeStream:
    def __init__(self, chunks, stop_reason):
        self.text_stream = iter(chunks)
        self._stop_reason = stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return SimpleNamespace(stop_reason=self._stop_reason)


def _fake_client(chunks, stop_reason="end_turn"):
    calls = []

    def stream(**kwargs):
        calls.append(kwargs)
        return _FakeStream(chunks, stop_reason)

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    return client, calls


def test_stream_document_yields_text():
    client, calls = _fake_client(["# Title\n", "Body"])
    assert "".join(stream_document(client, build_client_explainer_input(["Sales Hub"]))) == "# Title\nBody"
    assert calls and calls[0]["max_tokens"] > 0


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_stream_document_raises_on_incomplete_document(stop_reason):
    client, _ = _fake_client(["partial"], stop_reason)
    with pytest.raises(DiscoveryError):
        list(stream_document(client, build_client_explainer_input(["Sales Hub"])))


def test_suggest_modules_reads_only_the_recommended_section():
    md = """# Discovery
## Current State — Processes
Marketing team sends newsletters by hand.
## Recommended HubSpot Modules
- **Sales Hub** — pipeline tracking; replaces the marketing handoff spreadsheet.
- **Operations Hub** — two-way ERP sync.
- CMS Hub: rebuild of the patient portal.
## Open Questions & Gaps
- Service Hub not discussed.
"""
    assert suggest_modules(md) == ["Sales Hub", "Operations Hub", "Content Hub (CMS)"]


def test_suggest_modules_empty_without_section():
    assert suggest_modules("# Doc\n## Executive Summary\nSales Hub") == []


def test_every_module_has_aliases():
    from core.discovery import _MODULE_ALIASES

    assert set(_MODULE_ALIASES) == set(HUBSPOT_MODULES)
