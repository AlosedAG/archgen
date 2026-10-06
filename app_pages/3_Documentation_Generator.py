"""Module 3 — Documentation Generator (API-driven, read-only)."""

from __future__ import annotations

import streamlit as st

from archscope_domain.docgen import DocumentationGenerator, snapshot_to_docx, snapshot_to_markdown
from core.doc_export_ui import save_to_library_button
from core.connections import hubspot_client, require_hubspot_token
from archscope_integrations.hubspot import HubSpotAPIError, HubSpotScopeError
from core.project_store import project_name_input
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Documentation Generator", layout="wide")
inject_global_css()
render_page_header(
    "Documentation Generator",
    "Documentation pack: "
    "Data dictionary, workflow inventory, association map, pipeline/stage list, and "
    "roles/permissions summary.",
)
st.info("Every call made is read-only.")

project_name_input(label="Project name (for saving results to the library)")

require_hubspot_token()

has_snapshot = "portal_snapshot" in st.session_state
button_label = "Refresh from portal" if has_snapshot else "Pull from portal"

if st.button(button_label, type="primary"):
    try:
        client = hubspot_client()
        generator = DocumentationGenerator(client)
        with st.spinner("Pulling schemas, properties, pipelines, workflows, owners, and teams..."):
            st.session_state["portal_snapshot"] = generator.build_snapshot()
    except ValueError as exc:
        st.error(str(exc))
    except HubSpotScopeError as exc:
        st.error(f"Missing scope or invalid token: {exc}")
    except HubSpotAPIError as exc:
        st.error(f"HubSpot API error: {exc}")

snapshot = st.session_state.get("portal_snapshot")

if snapshot:
    st.divider()
    st.caption(f"Snapshot pulled at {snapshot.pulled_at}")

    for w in snapshot.warnings:
        st.warning(w)

    st.subheader("Data dictionary")
    for schema in snapshot.object_schemas:
        kind = "Custom" if schema.is_custom else "Standard"
        with st.expander(f"{schema.label} ({kind}, {schema.object_type}) — {len(schema.properties)} properties"):
            if schema.properties:
                st.dataframe(
                    [
                        {
                            "Property": p.name,
                            "Label": p.label,
                            "Type": p.type,
                            "Field Type": p.field_type,
                            "Group": p.group_name,
                            "Options": ", ".join(p.options),
                        }
                        for p in schema.properties
                    ],
                    use_container_width=True,
                )
            else:
                st.write("No properties returned.")

    st.subheader("Workflow inventory")
    if snapshot.workflows:
        st.dataframe(
            [
                {
                    "Name": w.name,
                    "Object Type": w.object_type,
                    "Enabled": w.enabled,
                    "Re-enrollment": w.re_enrollment_enabled,
                    "Actions": len(w.actions),
                }
                for w in snapshot.workflows
            ],
            use_container_width=True,
        )
    else:
        st.write("No workflows returned.")

    st.subheader("Association map")
    st.caption(
        "Association definitions shown here come from each custom object's schema. "
        "Default associations between standard objects are not exposed by this endpoint "
        "and are omitted."
    )
    assoc_rows = [
        {"From": a.from_object, "To (type ID)": a.to_object, "Label": a.label}
        for schema in snapshot.object_schemas
        for a in schema.associations
    ]
    if assoc_rows:
        st.dataframe(assoc_rows, use_container_width=True)
    else:
        st.write("None found.")

    st.subheader("Pipelines & stages")
    if snapshot.pipelines:
        for pl in snapshot.pipelines:
            st.markdown(f"**{pl.label}** ({pl.object_type})")
            st.dataframe(
                [{"Order": s.display_order, "Stage": s.label} for s in pl.stages],
                use_container_width=True,
            )
    else:
        st.write("No pipelines returned.")

    st.subheader("Roles & permissions summary")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Teams**")
        if snapshot.teams:
            st.dataframe(
                [{"Team": t.name, "Member Count": t.member_count} for t in snapshot.teams],
                use_container_width=True,
            )
        else:
            st.write("No teams returned.")
    with col2:
        st.markdown("**Owners**")
        if snapshot.owners:
            st.dataframe(
                [
                    {"Name": f"{o.first_name} {o.last_name}".strip(), "Email": o.email, "Teams": ", ".join(o.teams), "Archived": o.archived}
                    for o in snapshot.owners
                ],
                use_container_width=True,
            )
        else:
            st.write("No owners returned.")

    st.divider()
    md = snapshot_to_markdown(snapshot)
    docx_buffer = snapshot_to_docx(snapshot)
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button("Download Markdown", data=md, file_name="portal_documentation.md", mime="text/markdown")
    with dl_col2:
        st.download_button(
            "Download .docx",
            data=docx_buffer,
            file_name="portal_documentation.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    save_to_library_button(
        {"md": md, "docx": docx_buffer.getvalue()},
        document_type="Documentation Pack",
        project_name=st.session_state.get("report_project_name", ""),
    )
else:
    st.write("No snapshot pulled yet.")
