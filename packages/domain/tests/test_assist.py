"""Suggestions fill blanks only: never overwrite, never duplicate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from archscope_domain import assist
from archscope_domain.proposal import default_proposal


def test_parse_json_tolerates_fences_and_chatter():
    assert assist.parse_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert assist.parse_json('{"stages": []}') == {"stages": []}
    with pytest.raises(assist.AssistError):
        assist.parse_json("no json here")


def test_merge_stages_takes_a_whole_pipeline_when_empty():
    rows, filled = assist.merge_stages(
        [],
        {"stages": [{"name": "Discovery", "forecast": "20%", "fields": "Budget, Timeline"}, {"name": "  "}]},
    )
    assert rows == [
        {
            "name": "Discovery",
            "forecast": 20.0,
            "entry_criteria": "",
            "exit_criteria": "",
            "actions": "",
            "automations": "",
            "fields": ["Budget", "Timeline"],
        }
    ]
    assert filled == 2


def test_merge_stages_fills_only_blank_cells_of_matching_stages():
    current = [
        {
            "name": "Discovery",
            "forecast": None,
            "entry_criteria": "Typed by me",
            "exit_criteria": "",
            "actions": "",
            "automations": "",
            "fields": [],
        },
        {
            "name": "Custom",
            "forecast": 50,
            "entry_criteria": "",
            "exit_criteria": "",
            "actions": "",
            "automations": "",
            "fields": [],
        },
    ]
    suggested = {
        "stages": [
            {
                "name": "discovery",
                "forecast": 10,
                "entry_criteria": "Model text",
                "exit_criteria": "Qualified",
                "fields": ["Budget"],
            },
            {"name": "Extra stage"},
        ]
    }
    rows, filled = assist.merge_stages(current, suggested)
    assert [r["name"] for r in rows] == ["Discovery", "Custom"]  # nothing added or removed
    assert rows[0]["entry_criteria"] == "Typed by me"
    assert rows[0]["exit_criteria"] == "Qualified"
    assert rows[0]["forecast"] == 10
    assert rows[0]["fields"] == ["Budget"]
    assert rows[1] == current[1]
    assert filled == 3


def test_merge_architecture_adds_values_and_keeps_existing():
    current = {
        "standard_objects": ["Contact"],
        "integrations": [],
        "custom_object_notes": "Mine",
        "record_volumes": {"Contact": 5},
    }
    merged, added = assist.merge_architecture(
        current,
        {
            "standard_objects": ["contact", "Deal"],
            "integrations": ["NetSuite"],
            "custom_object_notes": "Model",
            "record_volumes": {"Contact": 99, "Deal": "1200"},
        },
    )
    assert merged["standard_objects"] == ["Contact", "Deal"]
    assert merged["integrations"] == ["NetSuite"]
    assert merged["custom_object_notes"] == "Mine"
    assert merged["record_volumes"] == {"Contact": 5, "Deal": 1200}
    assert added == 3


def test_merge_proposal_writes_blanks_and_skips_rows_already_there():
    p = default_proposal()
    p["problem_statement"] = "Typed by me"
    p["assumptions"] = [{"Assumption": "Client provides portal access."}]
    merged, changed = assist.merge_proposal(
        p,
        {
            "problem_statement": "Model text",
            "executive_summary": "Summary",
            "assumptions": ["client provides portal access", "Data is exported as CSV."],
            "scope": [{"status": "out of scope", "item": "Website rebuild"}],
        },
    )
    assert merged["problem_statement"] == "Typed by me"
    assert merged["executive_summary"] == "Summary"
    assert [a["Assumption"] for a in merged["assumptions"]] == ["Client provides portal access.", "Data is exported as CSV."]
    scope = [s for s in merged["scope"] if s["Item"]]
    assert scope[-1]["Status"] == "Out of Scope"
    assert scope[-1]["ID"].startswith("S-")
    assert set(changed) >= {"executive_summary", "assumptions", "scope"}
    assert "problem_statement" not in changed


def test_ask_claude_reads_text_blocks_and_checks_stop_reason():
    class Messages:
        def __init__(self, stop: str):
            self.stop = stop

        def create(self, **kwargs):
            assert kwargs["system"] == assist.SYSTEM_PROMPT
            return SimpleNamespace(stop_reason=self.stop, content=[SimpleNamespace(type="text", text='{"stages": []}')])

    assert assist.ask_claude(SimpleNamespace(messages=Messages("end_turn")), "stage_planner", {}, []) == {"stages": []}
    with pytest.raises(assist.AssistError):
        assist.ask_claude(SimpleNamespace(messages=Messages("max_tokens")), "stage_planner", {}, [])


def test_ask_gemini_moves_past_a_busy_model():
    calls = []

    class Busy(Exception):
        pass

    class Models:
        def generate_content(self, *, model, **_):
            calls.append(model)
            if model == "a":
                raise Busy()
            return SimpleNamespace(text='{"x": 1}')

    result, model = assist.ask_gemini(
        SimpleNamespace(models=Models()),
        "proposal",
        {},
        {},
        models=["a", "b"],
        classify=lambda e: "retry" if isinstance(e, Busy) else None,
    )
    assert (result, model, calls) == ({"x": 1}, "b", ["a", "b"])
