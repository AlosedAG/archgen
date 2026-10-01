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
    SECTIONS,
    SYSTEM_PROMPT,
    DiscoveryError,
    build_business_analysis_input,
    build_client_explainer_input,
    build_request,
    empty_notes,
    has_any_notes,
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
    notes["Goals"]["answers"]["kpis"] = "  lead-to-patient rate  "
    payload = build_business_analysis_input(notes, client_name="Bright Smiles", business_type="dental")

    assert payload["mode"] == MODE_BUSINESS_ANALYSIS
    assert payload["client"] == {"name": "Bright Smiles", "business_type": "dental"}
    assert list(payload["sections"]) == list(SECTIONS)
    goals = payload["sections"]["Goals"]["answers"]
    assert goals["KPIs — how will they measure success?"] == "lead-to-patient rate"
    # Blank answers are sent as "" (they become follow-up gaps), not dropped.
    assert len(goals) == len(SECTIONS["Goals"])
    assert goals["Timeline / key dates"] == ""


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
