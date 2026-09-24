"""Home — landing page. Routed to by Home.py via st.navigation."""

from __future__ import annotations

import streamlit as st

from core.hubspot_client import get_token
from core.theme import inject_global_css, render_hero, render_page_header

st.set_page_config(page_title="ArchitectureScope", layout="wide")
inject_global_css()

render_hero(
    title_html="Understand Your HubSpot Environment",
    subtitle=(
        "Review architecture, audit live portal for risk and drift, "
        "generate hand-off documentation, plain-language client report "
    ),
    cta_label="Start",
    cta_href="/Architecture_Generator",
)

st.markdown(
    "This tool never writes to HubSpot. Every API call it makes is read-only — it never "
    "creates, updates, or deletes anything in a connected portal."
)
st.caption(
    "The sidebar is grouped by what each page does: **Architecture & Planning** (design a new "
    "build), **Auditing** (assess a live portal), **Documentation** (generate hand-off records), "
    "and **Library** (everything saved so far)."
)

st.divider()

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    with st.container(border=True):
        st.markdown("### 1. Architecture Generator")
        st.write(
            "Answer questions about a project — object model needs, "
            "pipelines, regions/currencies, integrations, record volume, and "
            "hubs in scope — and gets a proposed architecture blueprint: custom "
            "objects, a property data dictionary, an association model, "
            "pipeline/stage definitions, a naming convention, and a suggested "
            "workflow list with overwrite-risk flags."
        )
        st.page_link("app_pages/1_Architecture_Generator.py", label="Open Architecture Generator")

with row1_col2:
    with st.container(border=True):
        st.markdown("### 2. Portal Auditor")
        st.write(
            "Connect to a live portal (read-only) and run best-practice checks "
            "against schemas, properties, pipelines, workflows, owners, and "
            "teams."
        )
        st.page_link("app_pages/2_Portal_Auditor.py", label="Open Portal Auditor")

with st.container(border=True):
    st.markdown("### 2B. Property Audit")
    st.write(
        "Connect to a live portal (read-only) and rate every object and every property Keep, "
        "Review, or Remove candidate, based on a sampled fill rate and workflow references. "
        "Exports a color-matched Excel workbook (Summary, Flagged for Action, All Properties, "
        "How to use) and a short PDF report — nothing is deleted or changed in HubSpot; every "
        "call is left for a human to make."
    )
    st.page_link("app_pages/2b_Property_Audit.py", label="Open Property Audit")

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    with st.container(border=True):
        st.markdown("### 3. Documentation Generator")
        st.write(
            "Connect to a live portal (read-only) and generate a documentation "
            "pack: data dictionary, workflow inventory, association map, "
            "pipeline/stage list, and roles/permissions summary."
        )
        st.page_link("app_pages/3_Documentation_Generator.py", label="Open Documentation Generator")

with row2_col2:
    with st.container(border=True):
        st.markdown("### 4. Executive Report")
        st.write(
            "Turns the portal snapshot and audit findings into a plain-language report."
        )
        st.page_link("app_pages/4_Executive_Report.py", label="Open Executive Report")

row3_col1, row3_col2 = st.columns(2)

with row3_col1:
    with st.container(border=True):
        st.markdown("### 5. Architecture Diagram")
        st.write(
            "Turns the blueprint and/or portal snapshot — with audit findings highlighted "
            "on it — into a visual, editable diagram of the objects in scope and how they "
            "connect. Export to diagrams.net for full drag-and-drop editing."
        )
        st.page_link("app_pages/5_Architecture_Diagram.py", label="Open Architecture Diagram")

with row3_col2:
    with st.container(border=True):
        st.markdown("### 6. Requirements Document")
        st.write(
            "Document a project's purpose, requirements, terminology, risks, plan, and open "
            "questions — the same structure as HubSpot's Written Requirements Document template."
        )
        st.page_link("app_pages/6_Requirements_Document.py", label="Open Requirements Document")

row4_col1, row4_col2 = st.columns(2)

with row4_col1:
    with st.container(border=True):
        st.markdown("### 7. Joint Evaluation Plan")
        st.write(
            "Track what needs to happen, when, and who's involved: team roster, milestones, "
            "technical/business needs, and open questions for an evaluation."
        )
        st.page_link("app_pages/7_Joint_Evaluation_Plan.py", label="Open Joint Evaluation Plan")

with row4_col2:
    with st.container(border=True):
        st.markdown("### 8. Test Case Document")
        st.write(
            "Track QA and UAT test cases — one row per requirement tested, with steps, "
            "expected/actual results, and feedback."
        )
        st.page_link("app_pages/8_Test_Case_Document.py", label="Open Test Case Document")

row5_col1, row5_col2 = st.columns(2)

with row5_col1:
    with st.container(border=True):
        st.markdown("### 9. Project Library")
        st.write(
            "Everything saved from every module, organized by project and document type, with "
            "the date each file was generated."
        )
        st.page_link("app_pages/9_Project_Library.py", label="Open Project Library")

st.divider()

render_page_header("Connection status")
token = get_token()
if token:
    st.success("HubSpot token detected (from HUBSPOT_TOKEN or this session). The Portal Auditor and Documentation Generator can connect now.")
else:
    st.warning(
        "No HubSpot token detected. Set the HUBSPOT_TOKEN environment "
        "variable, or enter a private app access token on the Portal. "
    )

st.caption(
    "See README for the exact private-app scopes each feature needs."
)
