"""Module 2 — Portal Auditor (API-driven, read-only)."""

from __future__ import annotations

import streamlit as st

from archscope_domain.audit import PortalAuditor, findings_to_csv, findings_to_markdown
from archscope_domain.docgen import DocumentationGenerator
from core.doc_export_ui import save_to_library_button
from core.connections import hubspot_client, require_hubspot_token
from archscope_integrations.hubspot import HubSpotAPIError, HubSpotScopeError
from core.project_store import project_name_input
from core.theme import inject_global_css, render_page_header
from archscope_domain.rules import RulesEngine

st.set_page_config(page_title="Portal Auditor", layout="wide")
inject_global_css()
render_page_header(
    "Portal Auditor",
    "Connects to a live HubSpot portal, read-only, and checks it against best practice: "
    "duplicate/near-duplicate properties, unused properties, required properties missing on "
    "a sample of records, orphaned/unassociated records (sampled), risky workflows, "
    "permission/team anomalies, and naming-convention drift against the Architecture "
    "Generator's rules.",
)
st.info("Every call made is read-only.")
st.caption(
    "Record-level checks (unused/required properties, orphaned records) sample up to "
    f"{RulesEngine().record_sample_size()} records per object rather than pulling everything, "
    "and say so in each finding."
)

project_name_input(label="Project name (for saving results to the library)")

require_hubspot_token()

has_snapshot = "portal_snapshot" in st.session_state
pull_col, audit_col = st.columns(2)

with pull_col:
    pull_label = "Refresh portal data" if has_snapshot else "Pull from portal"
    if st.button(pull_label, type="primary"):
        try:
            client = hubspot_client()
            generator = DocumentationGenerator(client)
            with st.spinner("Pulling schemas, properties, pipelines, workflows, owners, and teams..."):
                st.session_state["portal_snapshot"] = generator.build_snapshot()
            st.session_state.pop("audit_findings", None)
        except ValueError as exc:
            st.error(str(exc))
        except HubSpotScopeError as exc:
            st.error(f"Missing scope or invalid token: {exc}")
        except HubSpotAPIError as exc:
            st.error(f"HubSpot API error: {exc}")

with audit_col:
    if st.button("Run audit", disabled=not has_snapshot):
        try:
            client = hubspot_client()
            auditor = PortalAuditor(client, RulesEngine())
            with st.spinner("Running checks (including sampled record-level checks)..."):
                st.session_state["audit_findings"] = auditor.run(st.session_state["portal_snapshot"])
        except ValueError as exc:
            st.error(str(exc))
        except HubSpotScopeError as exc:
            st.error(f"Missing scope or invalid token: {exc}")
        except HubSpotAPIError as exc:
            st.error(f"HubSpot API error: {exc}")

if not has_snapshot:
    st.write("Pull from a portal first, then run the audit.")

snapshot = st.session_state.get("portal_snapshot")
if snapshot:
    for w in snapshot.warnings:
        st.warning(w)

findings = st.session_state.get("audit_findings")

if findings is not None:
    st.divider()
    st.subheader(f"Findings ({len(findings)})")

    if findings:
        areas = sorted({f.area for f in findings})
        severities = ["High", "Medium", "Low"]

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            selected_severities = st.multiselect("Filter by severity", severities, default=severities)
        with filter_col2:
            selected_areas = st.multiselect("Filter by area", areas, default=areas)

        filtered = [f for f in findings if f.severity in selected_severities and f.area in selected_areas]
        filtered.sort(key=lambda f: {"High": 0, "Medium": 1, "Low": 2}.get(f.severity, 3))

        st.dataframe(
            [
                {
                    "Severity": f.severity,
                    "Area": f.area,
                    "Object": f.object_type,
                    "Description": f.description,
                    "Recommended Fix": f.recommended_fix,
                }
                for f in filtered
            ],
            use_container_width=True,
        )

        st.divider()
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "Download CSV", data=findings_to_csv(filtered), file_name="audit_findings.csv", mime="text/csv"
            )
        with dl_col2:
            st.download_button(
                "Download Markdown",
                data=findings_to_markdown(filtered),
                file_name="audit_findings.md",
                mime="text/markdown",
            )
        save_to_library_button(
            {"csv": findings_to_csv(filtered), "md": findings_to_markdown(filtered)},
            document_type="Portal Audit Findings",
            project_name=st.session_state.get("report_project_name", ""),
        )
    else:
        st.success("No findings — the portal looks clean against the checks this tool runs.")
