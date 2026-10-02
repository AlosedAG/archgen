"""Module 8 — Test Case Document (QA / UAT).

Tracks the two testing rounds run against a beta HubSpot build — internal
Quality Assurance (QA) and customer User Acceptance Testing (UAT) — one
row per test case, with steps, expected/actual results, and feedback.
Matches HubSpot's own Test Case Document template.

Entirely self-contained: it works with a blank table. If a Written
Requirements Document already exists in this session, its Customer
Requirements list can optionally be loaded in as a starting point — a
one-off prefill, not a live link, so editing the WRD afterward has no
effect here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.doc_export_ui import render_sections_export
from archscope_domain.exporters import clean_rows
from core.project_store import guess_project_name
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Test Case Document", layout="wide")
inject_global_css()
render_page_header(
    "Test Case Document",
    "One row per test case, covering both testing rounds: internal QA first, then customer UAT. "
    "Use the Round column to tell them apart.",
)

ROUND_OPTIONS = ["QA", "UAT"]
RESULT_OPTIONS = ["Not Tested", "Met Expectations", "Issues Identified"]
_BLANK_ROW = {
    "Requirement": "",
    "Test Case Description": "",
    "Steps to Test": "",
    "Expected Result": "",
    "Round": "QA",
    "Actual Result": "Not Tested",
    "Actual Result Details": "",
    "Feedback / Notes": "",
}

st.session_state.setdefault("tcd_project_name", guess_project_name())
st.session_state.setdefault("tcd_rows_seed", [dict(_BLANK_ROW) for _ in range(3)])
st.session_state.setdefault("tcd_version", 0)

st.text_input("Project name", key="tcd_project_name")

wrd_requirements = st.session_state.get("wrd_requirements_snapshot")
load_col, note_col = st.columns([1, 2])
with load_col:
    if st.button("Load requirements from Requirements Document", disabled=not wrd_requirements):
        new_rows = [
            {**_BLANK_ROW, "Requirement": f"Customer Requirement {i}: {r.get('Requirement', '')}"}
            for i, r in enumerate(wrd_requirements, start=1)
        ]
        st.session_state["tcd_rows_seed"] = st.session_state["tcd_rows_seed"] + new_rows
        st.session_state["tcd_version"] += 1
with note_col:
    if not wrd_requirements:
        st.caption("No Requirements Document found in this session — fill in the table manually, or fill out the Requirements Document page first to prefill from it.")

st.divider()
st.subheader("Test Cases")
version = st.session_state["tcd_version"]
rows_df = st.data_editor(
    pd.DataFrame(st.session_state["tcd_rows_seed"]),
    key=f"tcd_rows_editor_{version}",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Requirement": st.column_config.TextColumn("Requirement", width="medium"),
        "Test Case Description": st.column_config.TextColumn("Test Case Description", width="large"),
        "Steps to Test": st.column_config.TextColumn("Steps to Test", width="large"),
        "Expected Result": st.column_config.TextColumn("Expected Result", width="medium"),
        "Round": st.column_config.SelectboxColumn("Round", options=ROUND_OPTIONS),
        "Actual Result": st.column_config.SelectboxColumn("Actual Result", options=RESULT_OPTIONS),
        "Actual Result Details": st.column_config.TextColumn("Actual Result Details", width="large"),
        "Feedback / Notes": st.column_config.TextColumn("Feedback / Notes", width="medium"),
    },
)

test_case_rows = clean_rows(rows_df, required_columns=["Requirement", "Test Case Description"])

st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Test cases", len(test_case_rows))
m2.metric("Met expectations", sum(1 for r in test_case_rows if r.get("Actual Result") == "Met Expectations"))
m3.metric("Issues identified", sum(1 for r in test_case_rows if r.get("Actual Result") == "Issues Identified"))
m4.metric("Not tested yet", sum(1 for r in test_case_rows if r.get("Actual Result") == "Not Tested"))

project_name = st.session_state["tcd_project_name"]
sections = [("Test Cases", test_case_rows)]

render_sections_export(
    doc_title=f"Test Case Document — {project_name or 'Untitled Project'}",
    subtitle="QA and UAT test cases for this HubSpot build, one row per requirement tested.",
    sections=sections,
    document_type="Test Case Document",
    project_name=project_name,
    file_stub=f"{project_name or 'untitled_project'}_test_cases".replace(" ", "_"),
)
