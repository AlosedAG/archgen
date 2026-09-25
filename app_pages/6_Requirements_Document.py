"""Module 6 — Written Requirements Document (WRD).

Structured intake that documents a customer's business objectives before
(or alongside) building an architecture: purpose and goals, numbered
customer requirements, project-specific terminology, known risks, a draft
project plan, open questions, and appendix links — the same sections as
HubSpot's own WRD template.

Entirely self-contained: it doesn't read from or require any other
module's output. If a blueprint or another document already named this
project, its name is offered as a starting guess for the project-name
field below, but every field here is plain manual entry either way.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.doc_export_ui import render_sections_export
from core.exporters import clean_rows
from core.project_store import guess_project_name
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Requirements Document", layout="wide")
inject_global_css()
render_page_header(
    "Written Requirements Document",
    "Document a project's purpose, requirements, terminology, risks, plan, and open questions — "
    "the same structure as HubSpot's own WRD template.",
)

DEFAULTS = {
    "wrd_project_name": guess_project_name(),
    "wrd_purpose": "",
    "wrd_goals": [{"Goal": ""}, {"Goal": ""}],
    "wrd_requirements": [{"Requirement": ""}, {"Requirement": ""}, {"Requirement": ""}],
    "wrd_definitions": [{"Term": "", "Definition": ""}, {"Term": "", "Definition": ""}],
    "wrd_risks": [{"Type": "Risk", "Description": ""}, {"Type": "Challenge", "Description": ""}],
    "wrd_plan": [
        {"Milestone": "", "Related Requirement": "", "Target Date": None, "Status": "Not Started"},
        {"Milestone": "", "Related Requirement": "", "Target Date": None, "Status": "Not Started"},
    ],
    "wrd_questions": [{"Question": ""}, {"Question": ""}],
    "wrd_appendix": [
        {"Resource Type": "Citation", "Link / Notes": ""},
        {"Resource Type": "Integration", "Link / Notes": ""},
        {"Resource Type": "Specification", "Link / Notes": ""},
        {"Resource Type": "Object field map", "Link / Notes": ""},
        {"Resource Type": "API", "Link / Notes": ""},
        {"Resource Type": "ERD", "Link / Notes": ""},
    ],
}
for _key, _value in DEFAULTS.items():
    st.session_state.setdefault(_key, _value)

st.text_input("Project name", key="wrd_project_name")

st.divider()
st.subheader("Project Overview")
st.text_area("Purpose", key="wrd_purpose", help="Summarize the purpose of the solutions development.")
st.caption("Goals")
goals_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_goals"]), key="wrd_goals_editor", num_rows="dynamic", use_container_width=True
)

st.divider()
st.subheader("Customer Requirements")
st.caption(
    "The functionality to be developed. Numbered order matters — the Test Case Document can "
    "optionally load these as a starting point for its test cases."
)
requirements_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_requirements"]),
    key="wrd_requirements_editor",
    num_rows="dynamic",
    use_container_width=True,
)
# Published under a plain (non-widget) key so other pages can read the
# current requirements list without depending on st.data_editor's
# internal session_state representation for keyed widgets.
st.session_state["wrd_requirements_snapshot"] = clean_rows(requirements_df)

st.divider()
st.subheader("Project Definitions")
st.caption("Terms based on the specific language the customer uses.")
definitions_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_definitions"]),
    key="wrd_definitions_editor",
    num_rows="dynamic",
    use_container_width=True,
)

st.divider()
st.subheader("Known Challenges or Risks")
risks_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_risks"]),
    key="wrd_risks_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={"Type": st.column_config.SelectboxColumn("Type", options=["Risk", "Challenge"])},
)

st.divider()
st.subheader("Project Plan")
st.caption("A draft for the execution team — not a commitment.")
plan_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_plan"]),
    key="wrd_plan_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Target Date": st.column_config.DateColumn("Target Date", format="YYYY-MM-DD"),
        "Status": st.column_config.SelectboxColumn(
            "Status", options=["Not Started", "In Progress", "Complete", "Blocked"]
        ),
    },
)

st.divider()
st.subheader("Open Questions")
questions_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_questions"]),
    key="wrd_questions_editor",
    num_rows="dynamic",
    use_container_width=True,
)

st.divider()
st.subheader("Appendix and Resources")
st.caption("Citations, integration details, specifications, object field maps, APIs, and diagram links.")
appendix_df = st.data_editor(
    pd.DataFrame(st.session_state["wrd_appendix"]),
    key="wrd_appendix_editor",
    num_rows="dynamic",
    use_container_width=True,
)

project_name = st.session_state["wrd_project_name"]
sections = [
    ("Project Overview", clean_rows(pd.DataFrame([{"Field": "Purpose", "Value": st.session_state["wrd_purpose"]}]))),
    ("Goals", clean_rows(goals_df)),
    ("Customer Requirements", clean_rows(requirements_df)),
    ("Project Definitions", clean_rows(definitions_df, required_columns=["Term"])),
    ("Known Challenges or Risks", clean_rows(risks_df, required_columns=["Description"])),
    ("Project Plan", clean_rows(plan_df, required_columns=["Milestone"])),
    ("Open Questions", clean_rows(questions_df)),
    ("Appendix and Resources", clean_rows(appendix_df, required_columns=["Link / Notes"])),
]

# Published under a plain key so the Proposal & SOW Builder can import this
# document's content (a one-off import there, not a live link).
st.session_state["wrd_export_snapshot"] = {"project_name": project_name, "sections": dict(sections)}

render_sections_export(
    doc_title=f"Written Requirements Document — {project_name or 'Untitled Project'}",
    subtitle="Documents the customer's business objectives for this HubSpot implementation.",
    sections=sections,
    document_type="Written Requirements Document",
    project_name=project_name,
    file_stub=f"{project_name or 'untitled_project'}_WRD".replace(" ", "_"),
)
