"""User Guide — the full in-app guide (``docs/user_guide.md``), plus the
PDF manuals in ``docs/`` as downloads. Each page also shows its own guide
section in the sidebar (see Home.py)."""

from __future__ import annotations

import streamlit as st

from core.guide import DOCS_DIR, guide_sections
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="User Guide", layout="wide")
inject_global_css()
render_page_header(
    "User guide",
    "How to use ArchitectureScope, step by step. Every other page also has its own instructions under "
    "**Guide for this page** at the bottom of the sidebar.",
)

sections = guide_sections()
OVERVIEW = ["Quick start", "The process, step by step"]
REFERENCE_ONLY = ["Troubleshooting"]
page_sections = [name for name in sections if name not in OVERVIEW + REFERENCE_ONLY]

start_tab, pages_tab, help_tab, downloads_tab = st.tabs(
    ["Start here", "Page by page", "Troubleshooting", "Downloads"]
)

with start_tab:
    for name in OVERVIEW:
        st.subheader(name)
        st.markdown(sections.get(name, ""))

with pages_tab:
    st.caption("In the same order as the sidebar.")
    for name in page_sections:
        with st.expander(name, expanded=False):
            st.markdown(sections[name])

with help_tab:
    for name in REFERENCE_ONLY:
        st.markdown(sections.get(name, ""))

with downloads_tab:
    st.caption("Printable manuals. The in-app guide above is the most up to date.")
    for filename, label in [
        ("ArchitectureScope_User_Guide.pdf", "ArchitectureScope user guide (PDF)"),
        ("Proposal_SOW_Builder_Manual.pdf", "Proposal & SOW Builder manual (PDF)"),
    ]:
        path = DOCS_DIR / filename
        if path.exists():
            st.download_button(label, data=path.read_bytes(), file_name=filename, mime="application/pdf", key=f"dl_{filename}")
    st.download_button(
        "This guide (Markdown)",
        data=(DOCS_DIR / "user_guide.md").read_text(encoding="utf-8"),
        file_name="ArchitectureScope_User_Guide.md",
        mime="text/markdown",
        key="dl_user_guide_md",
    )
