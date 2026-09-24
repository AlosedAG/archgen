"""Streamlit-coupled rendering for a saved Architecture Diagram snapshot
(see ``core.project_store.save_snapshot``) — the diagram, its at-a-glance
metrics, the properties-per-object and findings charts, and the objects/
connections tables, all reconstructed from the saved JSON rather than
live session state.

Shared by two pages: the Project Library (browsing any saved project) and
the Architecture Diagram page itself (so a user can pull up a previous
save without first regenerating a blueprint or re-pulling a portal
snapshot). Kept separate from ``core.diagram`` so that module can stay
plain-Python/UI-free.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from core.diagram import nodes_edges_from_dicts, to_graphviz


def render_diagram_snapshot(data: dict) -> None:
    nodes, edges = nodes_edges_from_dicts(data.get("nodes", []), data.get("edges", []))
    saved_at = (data.get("saved_at") or "")[:19].replace("T", " ")
    st.caption(
        f"Saved {saved_at} UTC · source: {data.get('source', '?')}"
        + (" · focused view" if data.get("focus") else "")
    )

    if not nodes:
        st.info("This saved diagram had no objects in it.")
        return

    st.graphviz_chart(to_graphviz(nodes, edges, show_labels=data.get("show_labels", True)), use_container_width=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Objects", len(nodes))
    m2.metric("Connections", len(edges))
    m3.metric("Custom objects", sum(1 for n in nodes if n.kind == "Custom"))
    m4.metric("Objects with findings", sum(1 for n in nodes if n.risk))

    st.caption("Properties per object")
    props_df = pd.DataFrame({"Object": [n.name for n in nodes], "Properties": [n.property_count for n in nodes]})
    st.bar_chart(props_df.set_index("Object"), use_container_width=True)

    sev_counts = data.get("findings_by_severity")
    area_counts = data.get("findings_by_area")
    if sev_counts or area_counts:
        chart_col1, chart_col2 = st.columns(2)
        if sev_counts:
            with chart_col1:
                st.caption("Findings by severity")
                st.bar_chart(
                    pd.DataFrame({"Severity": list(sev_counts.keys()), "Count": list(sev_counts.values())}).set_index(
                        "Severity"
                    ),
                    use_container_width=True,
                )
        if area_counts:
            with chart_col2:
                st.caption("Findings by area")
                st.bar_chart(
                    pd.DataFrame({"Area": list(area_counts.keys()), "Count": list(area_counts.values())}).set_index(
                        "Area"
                    ),
                    use_container_width=True,
                )

    table_col1, table_col2 = st.columns(2)
    with table_col1:
        st.caption("Objects")
        st.dataframe([asdict(n) for n in nodes], use_container_width=True)
    with table_col2:
        st.caption("Connections")
        st.dataframe([asdict(e) for e in edges], use_container_width=True)
