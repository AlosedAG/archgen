"""Module 4 — Executive Report.

Turns a pulled portal snapshot (Module 3) and, if available, audit findings
(Module 2) — both already sitting in ``st.session_state`` — into a
plain-language report: what the portal has, how it's structured, and
what's worth fixing. Produces a polished client-facing .docx and a
full-detail internal-facing .docx.

This page makes no HubSpot API calls of its own — it only reads data
already pulled on the Documentation Generator / Portal Auditor pages.
"""

from __future__ import annotations

import streamlit as st

from core.doc_export_ui import save_to_library_button
from core.models import SEVERITIES
from core.report import (
    AREA_EXPLANATIONS,
    SEVERITY_META,
    build_report_context,
    report_to_client_docx,
    report_to_internal_docx,
)
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Executive Report", layout="wide")
inject_global_css()
render_page_header(
    "Executive Report",
    "What the portal has, how it's structured, and what's worth fixing. Produces a polished client "
    "version and a full-detail internal version.",
)

snapshot = st.session_state.get("portal_snapshot")
findings = st.session_state.get("audit_findings")

if not snapshot:
    st.info("No portal snapshot yet. Pull one from the Documentation Generator or Portal Auditor page first.")
    st.page_link("app_pages/3_Documentation_Generator.py", label="Open Documentation Generator")
    st.page_link("app_pages/2_Portal_Auditor.py", label="Open Portal Auditor")
    st.stop()

if findings is None:
    st.warning(
        "No audit has been run yet — this report will describe the portal's structure, but "
        "the 'Things worth fixing' section will be empty until you run the audit."
    )
    st.page_link("app_pages/2_Portal_Auditor.py", label="Open Portal Auditor")

project_name = st.text_input(
    "Client / project name (optional)",
    value=st.session_state.get("report_project_name", ""),
    help="Used to personalize the report title. Leave blank for a generic title.",
    key="report_project_name",
)

ctx = build_report_context(snapshot, findings, project_name=project_name)

st.divider()

col1, col2, col3 = st.columns(3)
col1.metric("Overall health", ctx.rating)
col2.metric("Findings", ctx.finding_total if ctx.audited else "—")
col3.metric("Objects / properties", f"{ctx.standard_object_count + ctx.custom_object_count} / {ctx.total_properties}")
st.caption(ctx.rating_reason)

st.subheader("What's in this portal")
st.dataframe(
    [
        {
            "Object": o.label,
            "Kind": "Custom" if o.is_custom else "Standard",
            "Properties": o.property_count,
            "Top data groups": ", ".join(f"{n} ({c})" for n, c in o.top_groups[:3]),
            "Connects to": ", ".join(o.association_targets) or "—",
        }
        for o in ctx.object_summaries
    ],
    use_container_width=True,
)

if ctx.pipeline_summaries:
    st.subheader("Pipelines")
    st.dataframe(
        [
            {"Object": p.object_type, "Pipelines": p.pipeline_count, "Total stages": p.total_stage_count}
            for p in ctx.pipeline_summaries
        ],
        use_container_width=True,
    )

st.subheader("Automation & people")
a_col, b_col = st.columns(2)
with a_col:
    st.write(
        f"**Workflows:** {ctx.workflow_total} total — {ctx.workflow_enabled} enabled, "
        f"{ctx.workflow_disabled} disabled, {ctx.workflow_unnamed} still using HubSpot's "
        "default 'Unnamed workflow' name."
    )
with b_col:
    st.write(
        f"**Users & teams:** {ctx.owner_total} owners ({ctx.owner_unassigned} not on a team, "
        f"{ctx.owner_archived} archived), {ctx.team_total} teams ({ctx.team_empty} with no members)."
    )

if ctx.audited:
    st.subheader("Things worth fixing")
    if not ctx.finding_groups:
        st.success("No issues found in this scan.")
    for sev in SEVERITIES:
        sev_groups = [g for g in ctx.finding_groups if g.severity == sev]
        if not sev_groups:
            continue
        with st.expander(f"{SEVERITY_META[sev]['label']} — {sum(g.count for g in sev_groups)} finding(s)"):
            st.caption(SEVERITY_META[sev]["tone"])
            for g in sev_groups:
                meta = AREA_EXPLANATIONS.get(g.area, {})
                st.markdown(f"**{meta.get('title', g.area)}** ({g.count})")
                if meta.get("impact"):
                    st.caption(meta["impact"])
                st.dataframe(
                    [
                        {"Object": f.object_type, "Description": f.description, "Recommended Fix": f.recommended_fix}
                        for f in g.items
                    ],
                    use_container_width=True,
                )

st.divider()
st.subheader("Download")
client_docx = report_to_client_docx(ctx).getvalue()
internal_docx = report_to_internal_docx(ctx).getvalue()
dl_col1, dl_col2 = st.columns(2)
with dl_col1:
    st.download_button(
        "Download client report (.docx)",
        data=client_docx,
        file_name="portal_report_client.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
    )
    st.caption("Polished, plain-language — safe to send to a client as-is.")
    save_to_library_button({"docx": client_docx}, document_type="Executive Report (Client)", project_name=project_name)
with dl_col2:
    st.download_button(
        "Download internal report (.docx)",
        data=internal_docx,
        file_name="portal_report_internal.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    st.caption("Full technical detail — every finding, raw property groups — for internal use/context.")
    save_to_library_button({"docx": internal_docx}, document_type="Executive Report (Internal)", project_name=project_name)
