"""ArchitectureScope — HubSpot discovery, architecture, audit, and documentation tool.

Streamlit multipage entry point. Run with:

    streamlit run Home.py

This file is only a router: it declares every page and groups them into
sidebar sections via ``st.navigation``, then hands off to whichever page
was selected. Each page module (under ``app_pages/``) still owns its own
``st.set_page_config`` / content.

The sidebar follows the order a project actually runs in, so a new user
can simply work top to bottom: **Start here** (connect API keys first,
then the user guide), then the numbered steps **Discover → Assess →
Design → Propose → Deliver & test**, with the **Project Library** last
(it's used throughout). File names under ``app_pages/`` keep their
original module numbers; the sidebar order lives only here.

Before anything else, ``core.auth.require_login`` shows the sign-in
screen (Google and/or username + password) and stops the script until a
user is signed in.

Three things run on every page, before the page itself:

- the page's own section of the user guide (``docs/user_guide.md``) is
  shown at the bottom of the sidebar, so instructions are always one click
  away without leaving the page;
- the floating **Feedback** button (``core/feedback_ui.py``) is added, so
  users can email a bug report or idea with screenshots from any page;
- Discovery Call Assistant notes (``disc_*`` keys) are re-saved, because
  Streamlit otherwise drops a widget's value as soon as the user switches
  to a page that doesn't render it — and losing live call notes mid-call
  is the one failure that page can't afford.
"""

from __future__ import annotations

import streamlit as st

from core.auth import require_login
from core.feedback_ui import render_feedback_widget
from core.guide import page_guide

require_login()

setup = st.Page("app_pages/0_Setup.py", title="Setup & API keys", url_path="Setup", default=True)
user_guide = st.Page("app_pages/12_User_Guide.py", title="User guide", url_path="User_Guide")

discovery_assistant = st.Page(
    "app_pages/11_Discovery_Call_Assistant.py", title="Discovery Call Assistant", url_path="Discovery_Call_Assistant"
)
requirements_document = st.Page(
    "app_pages/6_Requirements_Document.py", title="Requirements Document", url_path="Requirements_Document"
)
joint_evaluation_plan = st.Page(
    "app_pages/7_Joint_Evaluation_Plan.py", title="Joint Evaluation Plan", url_path="Joint_Evaluation_Plan"
)

portal_auditor = st.Page("app_pages/2_Portal_Auditor.py", title="Portal Auditor", url_path="Portal_Auditor")
property_audit = st.Page("app_pages/2b_Property_Audit.py", title="Property Audit", url_path="Property_Audit")
documentation_generator = st.Page(
    "app_pages/3_Documentation_Generator.py", title="Documentation Generator", url_path="Documentation_Generator"
)
executive_report = st.Page("app_pages/4_Executive_Report.py", title="Executive Report", url_path="Executive_Report")

architecture_generator = st.Page(
    "app_pages/1_Architecture_Generator.py", title="Architecture Generator", url_path="Architecture_Generator"
)
architecture_diagram = st.Page(
    "app_pages/5_Architecture_Diagram.py", title="Architecture Diagram", url_path="Architecture_Diagram"
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
        "Start here": [setup, user_guide],
        "Step 1 · Discover": [discovery_assistant, requirements_document, joint_evaluation_plan],
        "Step 2 · Assess current portal": [portal_auditor, property_audit, documentation_generator, executive_report],
        "Step 3 · Design": [architecture_generator, architecture_diagram],
        "Step 4 · Propose": [proposal_builder],
        "Step 5 · Deliver & test": [test_case_document],
        "Library": [project_library],
    }
)

for _key in [k for k in st.session_state.keys() if str(k).startswith("disc_")]:
    st.session_state[_key] = st.session_state[_key]

_guide = page_guide(pg.title)
if _guide:
    with st.sidebar:
        with st.expander("📖 Guide for this page"):
            st.markdown(_guide)
            st.page_link(user_guide, label="Open the full user guide")

# Floating Feedback button (bottom-right) on every page, for signed-in users.
render_feedback_widget(pg.title)

pg.run()
