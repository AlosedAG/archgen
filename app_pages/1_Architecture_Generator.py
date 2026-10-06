"""Module 1 — Architecture Generator (input-driven, no API needed)."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from archscope_domain.blueprint import BlueprintGenerator, blueprint_to_json, blueprint_to_markdown
from core.doc_export_ui import save_to_library_button
from archscope_domain.models import BlueprintInput
from core.theme import inject_global_css, render_page_header
from archscope_domain.rules import RulesEngine

st.set_page_config(page_title="Architecture Generator", layout="wide")
inject_global_css()
render_page_header("Architecture Generator", "Answer a few questions about the project. No HubSpot API access required.")

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_inputs" / "example_project.json"

STANDARD_OBJECT_OPTIONS = ["Contact", "Company", "Deal", "Location", "Child", "Family"]
CUSTOM_OBJECT_KEYWORD_OPTIONS = ["Membership", "Subscription", "Location", "Event"]
INTEGRATION_OPTIONS = ["MyStudio", "Sakari", "Payments Provider", "Other"]
REGION_OPTIONS = ["United States", "Canada", "United Kingdom", "European Union", "Australia", "Other"]
CURRENCY_OPTIONS = ["USD", "CAD", "GBP", "EUR", "AUD", "Other"]
HUB_OPTIONS = ["Marketing Hub", "Sales Hub", "Service Hub", "CMS Hub", "Operations Hub", "Commerce Hub"]

DEFAULTS = {
    "gen_project_name": "",
    "gen_standard_objects": ["Contact", "Company", "Deal", "Location", "Child", "Family"],
    "gen_custom_object_keywords": [],
    "gen_custom_object_notes": "",
    "gen_pipelines_required": [],
    "gen_regions": [],
    "gen_currencies": ["USD"],
    "gen_integrations": [],
    "gen_other_integration_notes": "",
    "gen_record_volumes_text": "",
    "gen_hubs_in_scope": [],
}
for _key, _value in DEFAULTS.items():
    st.session_state.setdefault(_key, _value)


def _load_sample() -> None:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    st.session_state["gen_project_name"] = data.get("project_name", "")
    st.session_state["gen_standard_objects"] = data.get("standard_objects", [])
    st.session_state["gen_custom_object_keywords"] = data.get("custom_object_keywords", [])
    st.session_state["gen_custom_object_notes"] = data.get("custom_object_notes", "")
    st.session_state["gen_pipelines_required"] = data.get("pipelines_required", [])
    st.session_state["gen_regions"] = data.get("regions", [])
    st.session_state["gen_currencies"] = data.get("currencies", [])
    st.session_state["gen_integrations"] = data.get("integrations", [])
    st.session_state["gen_other_integration_notes"] = data.get("other_integration_notes", "")
    volumes = data.get("record_volumes", {})
    st.session_state["gen_record_volumes_text"] = "\n".join(f"{k}: {v}" for k, v in volumes.items())
    st.session_state["gen_hubs_in_scope"] = data.get("hubs_in_scope", [])


st.button(
    "Load sample project",
    on_click=_load_sample,
    help="Populate the form with the bundled example in sample_inputs/example_project.json",
)

st.divider()

st.text_input("Project name", key="gen_project_name")

col_a, col_b = st.columns(2)
with col_a:
    st.multiselect("Standard objects in scope", STANDARD_OBJECT_OPTIONS, key="gen_standard_objects")
    st.multiselect(
        "Custom object needs",
        CUSTOM_OBJECT_KEYWORD_OPTIONS,
        key="gen_custom_object_keywords",
        help="Recognized patterns get a full template (properties + associations). Anything else, describe below.",
    )
    st.text_area(
        "Other custom object notes",
        key="gen_custom_object_notes",
        help="Free text for custom object needs not covered by the list above. Flagged for manual review, not auto-modeled.",
    )
with col_b:
    st.multiselect("Regions", REGION_OPTIONS, key="gen_regions")
    st.multiselect("Currencies in scope", CURRENCY_OPTIONS, key="gen_currencies")
    st.multiselect("Hubs in scope", HUB_OPTIONS, key="gen_hubs_in_scope")

# Pipeline choices depend on objects picked above; guard against a stale
# selection referencing an object that was just removed.
_pipeline_choices = ["Deal", "Ticket"] + list(st.session_state["gen_custom_object_keywords"])
st.session_state["gen_pipelines_required"] = [
    p for p in st.session_state["gen_pipelines_required"] if p in _pipeline_choices
]
st.multiselect(
    "Pipelines required (choose the objects that need a pipeline)",
    _pipeline_choices,
    key="gen_pipelines_required",
    help="Options are derived from the standard/custom objects selected above.",
)

st.multiselect("Integrations", INTEGRATION_OPTIONS, key="gen_integrations")
st.text_input("Other integration notes (name it if you picked 'Other')", key="gen_other_integration_notes")

st.text_area(
    "Estimated record volumes (one per line, format 'Object: count')",
    key="gen_record_volumes_text",
    height=100,
    help="e.g.\nContact: 45000\nDeal: 12000",
)

generate = st.button("Generate blueprint", type="primary")

if generate:
    record_volumes: dict[str, int] = {}
    for line in st.session_state["gen_record_volumes_text"].splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        obj, _, count = line.partition(":")
        obj = obj.strip()
        count = count.strip().replace(",", "")
        if obj and count.isdigit():
            record_volumes[obj] = int(count)

    bp_input = BlueprintInput(
        project_name=st.session_state["gen_project_name"] or "Untitled Project",
        standard_objects=list(st.session_state["gen_standard_objects"]),
        custom_object_keywords=list(st.session_state["gen_custom_object_keywords"]),
        custom_object_notes=st.session_state["gen_custom_object_notes"],
        pipelines_required=list(st.session_state["gen_pipelines_required"]),
        regions=list(st.session_state["gen_regions"]),
        currencies=list(st.session_state["gen_currencies"]),
        integrations=list(st.session_state["gen_integrations"]),
        other_integration_notes=st.session_state["gen_other_integration_notes"],
        record_volumes=record_volumes,
        hubs_in_scope=list(st.session_state["gen_hubs_in_scope"]),
    )

    engine = RulesEngine()
    generator = BlueprintGenerator(engine)
    st.session_state["blueprint"] = generator.generate(bp_input)

blueprint = st.session_state.get("blueprint")

if blueprint:
    st.divider()
    st.header(f"Blueprint: {blueprint.project_name}")
    st.caption(f"Generated at {blueprint.generated_at}")

    for w in blueprint.warnings:
        st.warning(w)

    st.subheader("Custom objects")
    if blueprint.custom_objects:
        st.dataframe(
            [
                {"Name": o.name, "Plural Label": o.plural_label, "Description": o.description}
                for o in blueprint.custom_objects
            ],
            use_container_width=True,
        )
    else:
        st.write("None suggested.")

    st.subheader("Data dictionary")
    dictionary_rows = []
    for obj_name, props in blueprint.standard_object_properties.items():
        for p in props:
            dictionary_rows.append(
                {
                    "Object": obj_name,
                    "Property": p.name,
                    "Label": p.label,
                    "Type": p.type,
                    "Required": p.required,
                    "Options": ", ".join(p.options or []),
                }
            )
    for co in blueprint.custom_objects:
        for p in co.properties:
            dictionary_rows.append(
                {
                    "Object": co.name,
                    "Property": p.name,
                    "Label": p.label,
                    "Type": p.type,
                    "Required": p.required,
                    "Options": ", ".join(p.options or []),
                }
            )
    st.dataframe(dictionary_rows, use_container_width=True)

    st.subheader("Association model")
    st.dataframe(
        [
            {"From": a.from_object, "To": a.to_object, "Label": a.label, "Cardinality": a.cardinality}
            for a in blueprint.associations
        ],
        use_container_width=True,
    )

    st.subheader("Pipelines & stages")
    if blueprint.pipelines:
        for pl in blueprint.pipelines:
            st.markdown(f"**{pl.name}** ({pl.object_type})")
            st.dataframe(
                [
                    {"Order": s.order, "Stage": s.name, "Closed": s.is_closed, "Won": s.is_won}
                    for s in sorted(pl.stages, key=lambda stage: stage.order)
                ],
                use_container_width=True,
            )
    else:
        st.write("None requested.")

    st.subheader("Naming conventions")
    st.json(blueprint.naming_conventions)
    st.write(blueprint.base_currency_note or "No currencies specified.")

    st.subheader("Suggested workflows")
    st.dataframe(
        [
            {
                "Name": w.name,
                "Object": w.object_type,
                "Trigger": w.trigger,
                "Action": w.action_summary,
                "Overwrite Risk": w.overwrite_risk,
                "Risk Reason": w.risk_reason,
            }
            for w in blueprint.workflows
        ],
        use_container_width=True,
    )

    st.divider()
    md = blueprint_to_markdown(blueprint)
    json_str = blueprint_to_json(blueprint)
    file_stub = blueprint.project_name.replace(" ", "_").replace("/", "-")
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "Download Markdown", data=md, file_name=f"{file_stub}_blueprint.md", mime="text/markdown"
        )
    with dl_col2:
        st.download_button(
            "Download JSON", data=json_str, file_name=f"{file_stub}_blueprint.json", mime="application/json"
        )
    save_to_library_button(
        {"md": md, "json": json_str}, document_type="Architecture Blueprint", project_name=blueprint.project_name
    )
