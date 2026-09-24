"""Module 7 — Joint Evaluation Plan (JEP).

A mutually agreed set of steps for a purchasing/evaluation decision:
what needs to happen, when, and who's involved — plus the team roster,
technical/business needs, and open questions, matching HubSpot's own JEP
template. By the end of an evaluation, a filled-out JEP is a record of
every interaction with its milestone, owner, and outcome.

Entirely self-contained: it doesn't read from or require any other
module's output.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.doc_export_ui import render_sections_export
from core.exporters import clean_rows
from core.project_store import guess_project_name
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Joint Evaluation Plan", layout="wide")
inject_global_css()
render_page_header(
    "Joint Evaluation Plan",
    "What needs to happen, when, and who's involved at each stage of an evaluation — team roster, "
    "milestones, technical/business needs, and open questions.",
)

STATUS_OPTIONS = ["Not Started", "In Progress", "Complete", "Blocked"]

DEFAULTS = {
    "jep_project_name": guess_project_name(),
    "jep_contact_name": "",
    "jep_contact_phone": "",
    "jep_contact_email": "",
    "jep_milestones": [
        {
            "Target Date": None,
            "Status": "Not Started",
            "Milestone": "",
            "Link / Recording": "",
            "Prospect Contact": "",
            "Owner (Solutions Partner)": "",
            "Outcome / Notes": "",
        }
        for _ in range(3)
    ],
    "jep_team": [
        {"Side": "Prospect", "Role": "", "Team Member": "", "Email": "", "Phone": "", "Country": ""},
        {"Side": "Solutions Partner", "Role": "", "Team Member": "", "Email": "", "Phone": "", "Country": ""},
    ],
    "jep_technical_needs": [{"Functionality": "", "Confirmed": False, "Notes / Links": ""} for _ in range(3)],
    "jep_business_needs": [{"Functionality": "", "Confirmed": False, "Notes / Links": ""} for _ in range(2)],
    "jep_questions": [{"Question": "", "Contact": "", "Notes / Links": ""} for _ in range(2)],
}
for _key, _value in DEFAULTS.items():
    st.session_state.setdefault(_key, _value)

col_a, col_b = st.columns(2)
with col_a:
    st.text_input("Prospect's company name", key="jep_project_name")
with col_b:
    st.caption("Solutions partner contact")
    st.text_input("Name", key="jep_contact_name", label_visibility="collapsed", placeholder="Contact name")
    st.text_input("Phone", key="jep_contact_phone", label_visibility="collapsed", placeholder="Contact phone")
    st.text_input("Email", key="jep_contact_email", label_visibility="collapsed", placeholder="Contact email")

st.divider()
st.subheader("Milestones")
st.caption("What needs to happen, when, and who's involved — the running record of the evaluation.")
milestones_df = st.data_editor(
    pd.DataFrame(st.session_state["jep_milestones"]),
    key="jep_milestones_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Target Date": st.column_config.DateColumn("Target Date", format="YYYY-MM-DD"),
        "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
    },
)

st.divider()
st.subheader("Team Members")
team_df = st.data_editor(
    pd.DataFrame(st.session_state["jep_team"]),
    key="jep_team_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={"Side": st.column_config.SelectboxColumn("Side", options=["Prospect", "Solutions Partner"])},
)

st.divider()
st.subheader("Technical Needs")
technical_df = st.data_editor(
    pd.DataFrame(st.session_state["jep_technical_needs"]),
    key="jep_technical_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={"Confirmed": st.column_config.CheckboxColumn("Confirmed")},
)

st.subheader("Business Needs")
business_df = st.data_editor(
    pd.DataFrame(st.session_state["jep_business_needs"]),
    key="jep_business_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={"Confirmed": st.column_config.CheckboxColumn("Confirmed")},
)

st.divider()
st.subheader("Questions")
questions_df = st.data_editor(
    pd.DataFrame(st.session_state["jep_questions"]),
    key="jep_questions_editor",
    num_rows="dynamic",
    use_container_width=True,
)

project_name = st.session_state["jep_project_name"]
contact_rows = clean_rows(
    pd.DataFrame(
        [
            {"Field": "Contact Name", "Value": st.session_state["jep_contact_name"]},
            {"Field": "Contact Phone", "Value": st.session_state["jep_contact_phone"]},
            {"Field": "Contact Email", "Value": st.session_state["jep_contact_email"]},
        ]
    )
)
sections = [
    ("Solutions Partner Contact", contact_rows),
    ("Milestones", clean_rows(milestones_df, required_columns=["Milestone"])),
    ("Team Members", clean_rows(team_df, required_columns=["Team Member"])),
    ("Technical Needs", clean_rows(technical_df, required_columns=["Functionality"])),
    ("Business Needs", clean_rows(business_df, required_columns=["Functionality"])),
    ("Questions", clean_rows(questions_df, required_columns=["Question"])),
]

render_sections_export(
    doc_title=f"Joint Evaluation Plan — {project_name or 'Untitled Project'}",
    subtitle="A mutually agreed set of steps for this evaluation: what needs to happen, when, and who's involved.",
    sections=sections,
    document_type="Joint Evaluation Plan",
    project_name=project_name,
    file_stub=f"{project_name or 'untitled_project'}_JEP".replace(" ", "_"),
)
