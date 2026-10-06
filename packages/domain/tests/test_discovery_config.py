"""Discovery question bank: the shipped config/discovery_options.yaml is
valid, and malformed edits are rejected with messages naming the entry."""

from __future__ import annotations

import os

import pytest

from archscope_domain.discovery_config import (
    DEFAULT_OTHER_OPTION,
    INPUT_TEXT,
    DiscoveryConfigError,
    load_question_bank,
    parse_question_bank,
)


def test_shipped_config_is_valid_and_keeps_the_four_sections():
    bank = load_question_bank()
    assert list(bank.sections) == ["Goals", "Data", "Processes", "Solutions Design"]
    ids = [q.key for questions in bank.sections.values() for q in questions]
    assert len(ids) == len(set(ids))
    # Phase 2's reference rules trigger on these.
    assert {"data_regions", "org_structure", "compliance"} <= set(ids)
    data_regions = next(q for q in bank.sections["Data"] if q.key == "data_regions")
    assert "EU / UK" in data_regions.options


def test_other_option_is_appended_once_and_last():
    bank = parse_question_bank(
        {"sections": {"Goals": [{"id": "kpis", "label": "KPIs", "input": "multiselect", "options": ["A", "Other (specify)"]}]}}
    )
    question = bank.sections["Goals"][0]
    assert question.options == ("A",)
    assert bank.choices(question) == ["A", DEFAULT_OTHER_OPTION]


def test_input_defaults_to_text():
    bank = parse_question_bank({"sections": {"Goals": [{"id": "why", "label": "Why?"}]}})
    assert bank.sections["Goals"][0].input == INPUT_TEXT
    assert not bank.sections["Goals"][0].is_choice


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"id": "Bad-Id", "label": "x"}, "snake_case"),
        ({"id": "a__b", "label": "x"}, "snake_case"),
        ({"id": "notes", "label": "x"}, "reserved"),
        ({"id": "q", "label": ""}, "'label' is required"),
        ({"id": "q", "label": "x", "input": "dropdown"}, "'input' must be one of"),
        ({"id": "q", "label": "x", "input": "select"}, "needs 'options'"),
        ({"id": "q", "label": "x", "input": "text", "options": ["a"]}, "can't have options"),
        ({"id": "q", "label": "x", "input": "select", "options": ["a", "a"]}, "duplicate option"),
    ],
)
def test_invalid_entries_are_reported(entry, expected):
    with pytest.raises(DiscoveryConfigError) as exc:
        parse_question_bank({"sections": {"Goals": [entry]}})
    assert any(expected in p for p in exc.value.problems), exc.value.problems


def test_all_problems_reported_together_including_duplicate_ids_across_sections():
    raw = {
        "sections": {
            "Goals": [{"id": "q", "label": "x"}, {"id": "bad id", "label": "y"}],
            "Data": [{"id": "q", "label": "z"}],
        }
    }
    with pytest.raises(DiscoveryConfigError) as exc:
        parse_question_bank(raw)
    assert len(exc.value.problems) == 2
    assert any("duplicate id (also used in Goals)" in p for p in exc.value.problems)


@pytest.mark.parametrize("raw", [None, {}, {"sections": {}}, {"sections": ["Goals"]}])
def test_missing_sections_rejected(raw):
    with pytest.raises(DiscoveryConfigError):
        parse_question_bank(raw)


def test_load_reports_missing_file_and_bad_yaml_and_reloads_on_edit(tmp_path):
    path = tmp_path / "options.yaml"
    with pytest.raises(DiscoveryConfigError, match="not found"):
        load_question_bank(path)
    path.write_text("sections: [unclosed", encoding="utf-8")
    with pytest.raises(DiscoveryConfigError, match="not valid YAML"):
        load_question_bank(path)
    path.write_text("sections:\n  Goals:\n    - {id: a, label: A}\n", encoding="utf-8")
    assert load_question_bank(path).sections["Goals"][0].label == "A"
    path.write_text("sections:\n  Goals:\n    - {id: a, label: Renamed, input: text}\n", encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert load_question_bank(path).sections["Goals"][0].label == "Renamed"
