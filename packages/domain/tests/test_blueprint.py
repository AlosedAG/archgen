import json
from pathlib import Path

import pytest

from archscope_domain.blueprint import BlueprintGenerator, blueprint_to_json, blueprint_to_markdown
from archscope_domain.models import BlueprintInput
from archscope_domain.rules import RulesEngine

SAMPLE_PATH = Path(__file__).resolve().parents[3] / "sample_inputs" / "example_project.json"


@pytest.fixture
def sample_input() -> BlueprintInput:
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return BlueprintInput(**data)


@pytest.fixture
def generator() -> BlueprintGenerator:
    return BlueprintGenerator(RulesEngine())


def test_sample_input_loads(sample_input: BlueprintInput):
    assert sample_input.project_name.startswith("Bright Path Wellness")
    assert "Membership" in sample_input.custom_object_keywords


def test_generate_produces_custom_objects(generator, sample_input):
    blueprint = generator.generate(sample_input)
    names = {o.name for o in blueprint.custom_objects}
    assert names == {"Membership", "Subscription", "Location"}


def test_generate_flags_custom_object_notes_as_warning(generator, sample_input):
    blueprint = generator.generate(sample_input)
    assert any("Class Session" in w for w in blueprint.warnings)


def test_generate_flags_multi_currency_warning(generator, sample_input):
    blueprint = generator.generate(sample_input)
    assert any("Multiple currencies" in w for w in blueprint.warnings)
    assert blueprint.base_currency_note.startswith("Base currency: USD")


def test_generate_builds_pipelines_with_stages(generator, sample_input):
    blueprint = generator.generate(sample_input)
    by_object = {p.object_type: p for p in blueprint.pipelines}
    assert set(by_object) == {"Deal", "Ticket", "Membership"}
    assert by_object["Deal"].name == "Deal Pipeline"
    assert any(s.is_won for s in by_object["Deal"].stages)
    # Membership has no dedicated template -> falls back to generic_custom
    assert [s.name for s in by_object["Membership"].stages] == ["New", "In Progress", "Completed", "Cancelled"]


def test_generate_builds_associations_for_custom_objects(generator, sample_input):
    blueprint = generator.generate(sample_input)
    membership_assocs = [a for a in blueprint.associations if a.from_object == "Membership"]
    assert membership_assocs
    assert membership_assocs[0].to_object == "Contact"


def test_generate_applies_integration_properties(generator, sample_input):
    blueprint = generator.generate(sample_input)
    contact_props = {p.name for p in blueprint.standard_object_properties["Contact"]}
    assert "mystudio_member_id" in contact_props
    assert "sms_opt_in" in contact_props
    deal_props = {p.name for p in blueprint.standard_object_properties["Deal"]}
    assert "payment_status" in deal_props


def test_generate_flags_at_least_one_overwrite_risk_workflow(generator, sample_input):
    blueprint = generator.generate(sample_input)
    assert any(w.overwrite_risk for w in blueprint.workflows)
    assert any(not w.overwrite_risk for w in blueprint.workflows)


def test_generate_with_minimal_input_has_no_custom_objects():
    generator = BlueprintGenerator(RulesEngine())
    minimal = BlueprintInput(project_name="Minimal Project", standard_objects=["Contact"])
    blueprint = generator.generate(minimal)
    assert blueprint.custom_objects == []
    assert blueprint.pipelines == []
    assert blueprint.base_currency_note == ""


def test_blueprint_json_round_trips(generator, sample_input):
    blueprint = generator.generate(sample_input)
    json_str = blueprint_to_json(blueprint)
    parsed = json.loads(json_str)
    assert parsed["project_name"] == blueprint.project_name
    assert len(parsed["custom_objects"]) == len(blueprint.custom_objects)
    assert parsed["inputs"]["project_name"] == sample_input.project_name


def test_blueprint_markdown_has_expected_sections(generator, sample_input):
    blueprint = generator.generate(sample_input)
    md = blueprint_to_markdown(blueprint)
    for heading in [
        "# Architecture Blueprint:",
        "## Custom Objects",
        "## Data Dictionary",
        "## Association Model",
        "## Pipelines & Stages",
        "## Naming Conventions",
        "## Base Currency",
        "## Suggested Workflows",
    ]:
        assert heading in md
