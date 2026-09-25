"""ArchitectureScope — HubSpot architecture, audit, and documentation tool.

Streamlit multipage entry point. Run with:

    streamlit run Home.py

This file is only a router: it declares every page and groups them into
sidebar sections via ``st.navigation``, then hands off to whichever page
was selected. Each page module (under ``app_pages/``) still owns its own
``st.set_page_config`` / content, unchanged from before this file existed —
Streamlit allows that as long as it's the first Streamlit call made while
that page's script runs, which ``st.navigation``/``pg.run()`` preserves.

Sections exist specifically so **Auditing** (assessing a live portal —
Portal Auditor, Property Audit, Executive Report) and **Documentation**
(generating hand-off records — Documentation Generator, WRD, JEP, Test
Case Document) read as clearly separate in the sidebar, rather than one
flat, undifferentiated list of nine-plus pages.
"""

from __future__ import annotations

import streamlit as st

home = st.Page("app_pages/0_Home.py", title="Home", default=True)

architecture_generator = st.Page(
    "app_pages/1_Architecture_Generator.py", title="Architecture Generator", url_path="Architecture_Generator"
)
architecture_diagram = st.Page(
    "app_pages/5_Architecture_Diagram.py", title="Architecture Diagram", url_path="Architecture_Diagram"
)

portal_auditor = st.Page("app_pages/2_Portal_Auditor.py", title="Portal Auditor", url_path="Portal_Auditor")
property_audit = st.Page("app_pages/2b_Property_Audit.py", title="Property Audit", url_path="Property_Audit")
executive_report = st.Page("app_pages/4_Executive_Report.py", title="Executive Report", url_path="Executive_Report")

documentation_generator = st.Page(
    "app_pages/3_Documentation_Generator.py", title="Documentation Generator", url_path="Documentation_Generator"
)
requirements_document = st.Page(
    "app_pages/6_Requirements_Document.py", title="Requirements Document", url_path="Requirements_Document"
)
joint_evaluation_plan = st.Page(
    "app_pages/7_Joint_Evaluation_Plan.py", title="Joint Evaluation Plan", url_path="Joint_Evaluation_Plan"
)
proposal_builder = st.Page(
    "app_pages/10_Proposal_SOW_Builder.py", title="Proposal & SOW Builder", url_path="Proposal_SOW_Builder"
)
test_case_document = st.Page(
    "app_pages/8_Test_Case_Document.py", title="Test Case Document", url_path="Test_Case_Document"
)

project_library = st.Page("app_pages/9_Project_Library.py", title="Project Library", url_path="Project_Library")

pg = st.navigation(
    {
        "": [home],
        "Architecture & Planning": [architecture_generator, architecture_diagram],
        "Auditing": [portal_auditor, property_audit, executive_report],
        "Documentation": [documentation_generator, requirements_document, joint_evaluation_plan, test_case_document],
        "Proposals": [proposal_builder],
        "Library": [project_library],
    }
)
pg.run()
