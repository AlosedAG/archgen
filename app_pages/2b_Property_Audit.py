"""Module 2B — Property Audit (API-driven, read-only)."""

from __future__ import annotations

import streamlit as st

from core.doc_export_ui import render_export_footer
from core.docgen import DocumentationGenerator
from core.connections import require_hubspot_token
from core.hubspot_client import HubSpotAPIError, HubSpotClient, HubSpotScopeError
from core.project_store import project_name_input
from core.property_audit import property_audit_to_pdf, property_audit_to_xlsx, run_property_audit
from core.theme import inject_global_css, render_page_header
from rules.engine import RulesEngine

st.set_page_config(page_title="Property Audit", layout="wide")
inject_global_css()
render_page_header(
    "Property Audit",
    "Detects every object and every property in a live portal and rates each one Keep, Review, "
    "or Remove candidate, based on a sampled fill rate and workflow references — then exports a "
    "color-matched Excel workbook and a short PDF report so a human can check the calls before "
    "anything is deleted in HubSpot.",
)
st.info("Every call made is read-only. Nothing is ever deleted, archived, or changed by this tool.")
st.caption(
    "Fill % comes from a sample of up to "
    f"{RulesEngine().record_sample_size()} records per object. Uses counts references found in this "
    "portal's workflow actions only — forms, lists, reports, and dashboards aren't pulled, so a "
    "property used only in one of those will still show 0 here. Only custom properties are ever "
    "flagged; native HubSpot properties are always Keep."
)

project_name_input(label="Project name (for saving results to the library)")

require_hubspot_token()

has_snapshot = "portal_snapshot" in st.session_state
pull_col, audit_col = st.columns(2)

with pull_col:
    pull_label = "Refresh portal data" if has_snapshot else "Pull from portal"
    if st.button(pull_label, type="primary"):
        try:
            client = HubSpotClient()
            generator = DocumentationGenerator(client)
            with st.spinner("Pulling schemas, properties, pipelines, workflows, owners, and teams..."):
                st.session_state["portal_snapshot"] = generator.build_snapshot()
            st.session_state.pop("property_audit_result", None)
        except ValueError as exc:
            st.error(str(exc))
        except HubSpotScopeError as exc:
            st.error(f"Missing scope or invalid token: {exc}")
        except HubSpotAPIError as exc:
            st.error(f"HubSpot API error: {exc}")

with audit_col:
    if st.button("Run property audit", type="primary", disabled=not has_snapshot):
        try:
            client = HubSpotClient()
            with st.spinner("Sampling records and rating every property..."):
                st.session_state["property_audit_result"] = run_property_audit(
                    client, st.session_state["portal_snapshot"], RulesEngine()
                )
        except ValueError as exc:
            st.error(str(exc))
        except HubSpotScopeError as exc:
            st.error(f"Missing scope or invalid token: {exc}")
        except HubSpotAPIError as exc:
            st.error(f"HubSpot API error: {exc}")

if not has_snapshot:
    st.write("Pull from a portal first, then run the property audit.")

snapshot = st.session_state.get("portal_snapshot")
if snapshot:
    for w in snapshot.warnings:
        st.warning(w)

result = st.session_state.get("property_audit_result")

if result is not None:
    st.divider()
    for w in result.warnings:
        st.warning(w)

    totals = result.totals
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Properties audited", totals.properties_count)
    m2.metric("Keep", totals.keep_count)
    m3.metric("Review", totals.review_count)
    m4.metric("Remove candidate", totals.remove_count)
    m5.metric("Cleanup score", f"{totals.cleanup_score}/100")

    st.subheader("Summary by object")
    st.dataframe(
        [
            {
                "Object": s.object_label,
                "Properties": s.properties_count,
                "Custom": s.custom_count,
                "Remove candidate": s.remove_count,
                "Review": s.review_count,
                "Keep": s.keep_count,
                "Cleanup score": s.cleanup_score,
            }
            for s in result.object_summaries
        ],
        use_container_width=True,
    )

    st.subheader(f"Flagged for action ({len(result.flagged_rows)})")
    st.caption("Custom properties rated Review or Remove candidate, worst first — this is the actual cleanup worklist.")
    if result.flagged_rows:
        objects = sorted({r.object_label for r in result.flagged_rows})
        selected_objects = st.multiselect("Filter by object", objects, default=objects)
        filtered = [r for r in result.flagged_rows if r.object_label in selected_objects]
        st.dataframe(
            [
                {
                    "Object": r.object_label,
                    "Property": r.property_label,
                    "Internal name": r.internal_name,
                    "Type": r.field_type,
                    "Fill %": r.fill_pct,
                    "Uses": r.uses,
                    "Rating": r.rating,
                    "Assessment": r.assessment,
                }
                for r in filtered
            ],
            use_container_width=True,
        )
    else:
        st.success("No custom properties flagged — every custom field is well filled or in active use.")

    st.divider()
    project_name = st.session_state.get("report_project_name", "")
    xlsx_bytes = property_audit_to_xlsx(result, project_name=project_name)
    pdf_bytes = property_audit_to_pdf(result, project_name=project_name)
    render_export_footer(
        {"xlsx": xlsx_bytes, "pdf": pdf_bytes},
        document_type="Property Audit",
        project_name=project_name,
        file_stub="property_audit",
    )
