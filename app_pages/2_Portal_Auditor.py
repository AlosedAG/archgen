"""Module 2 — Portal Auditor (API-driven, read-only)."""

from __future__ import annotations

import streamlit as st

from core.audit import PortalAuditor, findings_to_csv, findings_to_markdown
from core.docgen import DocumentationGenerator
from core.doc_export_ui import save_to_library_button
from core.hubspot_client import HubSpotAPIError, HubSpotClient, HubSpotScopeError, get_token
from core.project_store import project_name_input
from core.theme import inject_global_css, render_page_header
from rules.engine import RulesEngine

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

if not get_token():
    with st.expander("How do I get a HubSpot API key?"):
        st.markdown(
            "1. In HubSpot, go to **Settings → Integrations → Private Apps**.\n"
            "2. Click **Create a private app**, give it a name (e.g. \"ArchitectureScope Audit\") "
            "on the **Basic Info** tab.\n"
            "3. On the **Scopes** tab, add the read scopes below — this tool never writes to "
            "your portal, so no write scopes are needed.\n"
            "4. Click **Create app**, confirm, then copy the generated **access token** "
            "(shown once) and paste it below.\n\n"
            "Full walkthrough: "
            "[developers.hubspot.com/docs/api/private-apps](https://developers.hubspot.com/docs/api/private-apps)."
        )
        st.markdown(
            "**Required scopes** (exact names occasionally shift in HubSpot's scope picker — "
            "if a pull fails with a scope error, the app will tell you which one's likely missing):\n\n"
            "| Used for | Scopes |\n"
            "|---|---|\n"
            "| Standard object schemas & properties | `crm.schemas.contacts.read`, "
            "`crm.schemas.companies.read`, `crm.schemas.deals.read`, `tickets` |\n"
            "| Custom object schemas & properties | `crm.schemas.custom.read` |\n"
            "| Record sampling (unused/required property & orphan checks) | "
            "`crm.objects.contacts.read`, `crm.objects.companies.read`, `crm.objects.deals.read`, "
            "`crm.objects.tickets.read`, `crm.objects.custom.read` |\n"
            "| Pipelines | covered by the object read scopes above |\n"
            "| Workflows (legacy Automation API) | `automation` |\n"
            "| Owners | `crm.objects.owners.read` |\n"
            "| Teams | `settings.users.teams.read` |\n\n"
            "You can grant a subset — the audit will report what it couldn't pull as a warning "
            "rather than failing outright."
        )
    st.text_input(
        "HubSpot private app access token",
        type="password",
        key="hubspot_token",
        help="Stored only in this session's memory — never written to disk or logged. "
        "You can also set the HUBSPOT_TOKEN environment variable instead.",
    )
else:
    st.success("HubSpot token detected.")

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
            client = HubSpotClient()
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
