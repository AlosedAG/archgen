"""Module 5 — Architecture Diagram.

Turns the Architecture Generator's blueprint (Module 1) and/or a pulled
portal snapshot (Module 2/3) — annotated with audit findings (Module 2)
when available — into a visual, entity-relationship-style diagram of the
objects in scope and how they connect. Findings are highlighted directly
on the diagram (a colored border on the object they were raised against).

The diagram is driven by two editable tables, not the raw source data
directly: the generator and the audit are both heuristic, so this page
lets a user fix anything they got wrong — rename an object, drop a
spurious connection, correct a cardinality — before rendering or
exporting. Edits live only in this session; "Reset to generated data"
throws them away and rebuilds from the current source.

This page makes no HubSpot API calls of its own.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core.diagram import (
    DiagramEdge,
    DiagramNode,
    dangling_edges,
    diagram_to_json,
    findings_by_area,
    findings_by_severity,
    from_blueprint,
    from_snapshot,
    to_drawio_xml,
    to_graphviz,
    to_png_bytes,
)
from core import project_store
from core.diagram_preview import render_diagram_snapshot
from core.doc_export_ui import save_to_library_button
from core.exporters import sections_to_csv, sections_to_xlsx
from core.project_store import project_name_input
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Architecture Diagram", layout="wide")
inject_global_css()
render_page_header(
    "Architecture Diagram",
    "A visual, editable map of the objects in this environment and how they connect — built from "
    "the Architecture Generator blueprint and/or a live portal snapshot, with audit findings "
    "highlighted directly on the diagram.",
)

SNAPSHOT_LABEL = "Live portal snapshot"
BLUEPRINT_LABEL = "Architecture blueprint"

blueprint = st.session_state.get("blueprint")
snapshot = st.session_state.get("portal_snapshot")
findings = st.session_state.get("audit_findings")

saved_diagram_projects = [
    p for p in project_store.list_projects() if "Architecture Diagram" in project_store.list_snapshot_types(p)
]
if saved_diagram_projects:
    with st.expander("View a previously saved diagram", expanded=not (blueprint or snapshot)):
        st.caption(
            "Pulls up the diagram, charts, and tables exactly as they were the last time this "
            "project was saved — no need to regenerate a blueprint or re-pull the portal."
        )
        picked_project = st.selectbox("Project", saved_diagram_projects, key="diagram_saved_project_picker")
        saved_data = project_store.load_snapshot(picked_project, "Architecture Diagram")
        if saved_data:
            render_diagram_snapshot(saved_data)
    st.divider()

if not blueprint and not snapshot:
    st.info("Nothing to diagram yet. Generate a blueprint or pull a live portal snapshot first.")
    st.page_link("app_pages/1_Architecture_Generator.py", label="Open Architecture Generator")
    st.page_link("app_pages/2_Portal_Auditor.py", label="Open Portal Auditor")
    st.page_link("app_pages/3_Documentation_Generator.py", label="Open Documentation Generator")
    st.stop()

source_options = ([SNAPSHOT_LABEL] if snapshot else []) + ([BLUEPRINT_LABEL] if blueprint else [])
if len(source_options) > 1:
    source = st.radio(
        "Diagram source",
        source_options,
        horizontal=True,
        help="A live snapshot reflects the real portal; the blueprint is the proposed design from the Architecture Generator.",
    )
else:
    source = source_options[0]
    st.caption(f"Source: {source}")

if source == SNAPSHOT_LABEL and findings is None:
    st.caption("No audit has been run yet — run one from the Portal Auditor to highlight findings on this diagram.")

include_engagements = False
if source == SNAPSHOT_LABEL:
    include_engagements = st.checkbox(
        "Include HubSpot activity objects (Task, Note, Email, Call, Meeting, etc.)",
        value=False,
        key="diagram_include_engagements",
        help="Off by default — these generic engagement types attach to almost every object on a "
        "real portal and mostly add clutter rather than architecture insight.",
    )

project_name = project_name_input(label="Project name (for saving this diagram to the library)")

seed_signature = (source, include_engagements)


def _seed_for(src: str, incl_engagements: bool) -> tuple[list[DiagramNode], list[DiagramEdge]]:
    if src == SNAPSHOT_LABEL:
        return from_snapshot(snapshot, findings, include_engagements=incl_engagements)
    return from_blueprint(blueprint)


def _reseed(signature: tuple[str, bool]) -> None:
    src, incl_engagements = signature
    nodes, edges = _seed_for(src, incl_engagements)
    st.session_state["diagram_seed_nodes"] = [asdict(n) for n in nodes]
    st.session_state["diagram_seed_edges"] = [asdict(e) for e in edges]
    st.session_state["diagram_seed_signature"] = signature
    st.session_state["diagram_version"] = st.session_state.get("diagram_version", 0) + 1


if st.session_state.get("diagram_seed_signature") != seed_signature:
    _reseed(seed_signature)

if st.button("Reset to generated data", help="Discard edits below and rebuild the tables from the current source."):
    _reseed(seed_signature)

version = st.session_state["diagram_version"]

st.divider()
st.subheader("Objects")
st.caption("Edit freely — rename, change kind or risk, add or delete rows. This feeds the diagram below.")
nodes_df = st.data_editor(
    pd.DataFrame(st.session_state["diagram_seed_nodes"]),
    key=f"diagram_nodes_editor_{version}",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "name": st.column_config.TextColumn("Name", required=True),
        "kind": st.column_config.SelectboxColumn("Kind", options=["Standard", "Custom", "Activity"], required=True),
        "property_count": st.column_config.NumberColumn("Properties", min_value=0, step=1),
        "risk": st.column_config.SelectboxColumn("Risk", options=["", "Low", "Medium", "High"]),
        "finding_count": st.column_config.NumberColumn("Findings", min_value=0, step=1),
        "notes": st.column_config.TextColumn("Notes"),
    },
)

st.subheader("Connections")
st.caption("From/To must match an object name above to be drawn on the diagram.")
edges_df = st.data_editor(
    pd.DataFrame(st.session_state["diagram_seed_edges"]),
    key=f"diagram_edges_editor_{version}",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "source": st.column_config.TextColumn("From", required=True),
        "target": st.column_config.TextColumn("To", required=True),
        "label": st.column_config.TextColumn("Label"),
        "cardinality": st.column_config.SelectboxColumn(
            "Cardinality", options=["one-to-one", "one-to-many", "many-to-one", "many-to-many"]
        ),
    },
)


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _num(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clean_nodes(df: pd.DataFrame) -> list[DiagramNode]:
    result = []
    for row in df.to_dict("records"):
        name = _text(row.get("name"))
        if not name:
            continue
        result.append(
            DiagramNode(
                name=name,
                kind=_text(row.get("kind")) or "Standard",
                property_count=_num(row.get("property_count")),
                risk=_text(row.get("risk")),
                finding_count=_num(row.get("finding_count")),
                notes=_text(row.get("notes")),
            )
        )
    return result


def _clean_edges(df: pd.DataFrame) -> list[DiagramEdge]:
    result = []
    for row in df.to_dict("records"):
        source_name = _text(row.get("source"))
        target_name = _text(row.get("target"))
        if not source_name or not target_name:
            continue
        result.append(
            DiagramEdge(
                source=source_name,
                target=target_name,
                label=_text(row.get("label")),
                cardinality=_text(row.get("cardinality")) or "many-to-many",
            )
        )
    return result


nodes = _clean_nodes(nodes_df)
edges = _clean_edges(edges_df)

st.divider()
focus_col, labels_col = st.columns([3, 1])
with focus_col:
    focus = st.multiselect(
        "Focus diagram on (optional)",
        options=sorted(n.name for n in nodes),
        default=[],
        key="diagram_focus",
        help="Narrows the diagram, charts, and exports below to just these objects and the "
        "connections between them, without touching the tables above. Leave empty to show everything.",
    )
with labels_col:
    show_labels = st.checkbox("Show connection labels", value=True, key="diagram_show_labels")

if focus:
    focus_set = set(focus)
    nodes = [n for n in nodes if n.name in focus_set]
    edges = [e for e in edges if e.source in focus_set and e.target in focus_set]

st.subheader("Diagram")
if not nodes:
    st.warning("No objects to diagram yet — add at least one row to the Objects table above, or clear the focus filter.")
else:
    st.graphviz_chart(to_graphviz(nodes, edges, show_labels=show_labels), use_container_width=True)

    dangling = dangling_edges(nodes, edges)
    if dangling:
        st.warning(
            "Not drawn — these connections reference an object that isn't in the table above (or is "
            "outside the current focus filter): " + "; ".join(f"{e.source} → {e.target}" for e in dangling)
        )

    legend_col1, legend_col2, legend_col3 = st.columns(3)
    with legend_col1:
        st.caption("Filled purple = custom object · white = standard object.")
    with legend_col2:
        st.caption("Dashed grey = HubSpot activity object (Task, Email, ...).")
    with legend_col3:
        st.caption("Border color = worst finding on that object — red High, orange Medium, yellow Low.")

st.divider()
st.subheader("At a glance")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Objects", len(nodes))
m2.metric("Connections", len(edges))
m3.metric("Custom objects", sum(1 for n in nodes if n.kind == "Custom"))
m4.metric("Objects with findings", sum(1 for n in nodes if n.risk))

if nodes:
    st.caption("Properties per object")
    props_df = pd.DataFrame({"Object": [n.name for n in nodes], "Properties": [n.property_count for n in nodes]})
    st.bar_chart(props_df.set_index("Object"), use_container_width=True)

if findings and source == SNAPSHOT_LABEL:
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.caption("Findings by severity")
        sev_counts = findings_by_severity(findings)
        st.bar_chart(
            pd.DataFrame({"Severity": list(sev_counts.keys()), "Count": list(sev_counts.values())}).set_index("Severity"),
            use_container_width=True,
        )
    with chart_col2:
        st.caption("Findings by area")
        area_counts = findings_by_area(findings)
        st.bar_chart(
            pd.DataFrame({"Area": list(area_counts.keys()), "Count": list(area_counts.values())}).set_index("Area"),
            use_container_width=True,
        )

st.divider()
st.subheader("Export")
st.caption(
    "The .drawio file opens in diagrams.net (app.diagrams.net) — a free, no-login editor — for full "
    "drag-and-drop editing: move objects, redraw connections, relabel anything. The PNG uses the same "
    "layout and is ready to drop straight into a slide or doc."
)
drawio_xml = to_drawio_xml(nodes, edges, show_labels=show_labels)
gv_source = to_graphviz(nodes, edges, show_labels=show_labels)


@st.cache_data(show_spinner=False)
def _cached_diagram_png(nodes: list[DiagramNode], edges: list[DiagramEdge], show_labels: bool) -> bytes:
    # Rendering pulls in matplotlib (a real one-time import cost) and does
    # actual layout/drawing work -- cache it so toggling an unrelated widget
    # elsewhere on the page doesn't re-render the same PNG on every rerun.
    return to_png_bytes(nodes, edges, show_labels=show_labels)


png_bytes = _cached_diagram_png(nodes, edges, show_labels) if nodes else b""
dl1, dl2, dl3, dl4 = st.columns(4)
with dl1:
    st.download_button(
        "Download diagrams.net file (.drawio)",
        data=drawio_xml,
        file_name="architecture_diagram.drawio",
        mime="application/xml",
        type="primary",
        disabled=not nodes,
    )
with dl2:
    st.download_button(
        "Download image (.png)",
        data=png_bytes,
        file_name="architecture_diagram.png",
        mime="image/png",
        disabled=not nodes,
    )
with dl3:
    st.download_button(
        "Download Graphviz source (.gv)",
        data=gv_source,
        file_name="architecture_diagram.gv",
        mime="text/vnd.graphviz",
        disabled=not nodes,
    )
with dl4:
    st.download_button(
        "Download edited data (.json)",
        data=diagram_to_json(nodes, edges),
        file_name="architecture_diagram.json",
        mime="application/json",
        disabled=not nodes,
    )

diagram_sections = [("Objects", [asdict(n) for n in nodes]), ("Connections", [asdict(e) for e in edges])]
xlsx_bytes = sections_to_xlsx(diagram_sections)
csv_text = sections_to_csv(diagram_sections)
dl4, dl5 = st.columns(2)
with dl4:
    st.download_button(
        "Download tables (.xlsx)",
        data=xlsx_bytes,
        file_name="architecture_diagram.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=not nodes,
    )
with dl5:
    st.download_button(
        "Download tables (.csv)", data=csv_text, file_name="architecture_diagram.csv", mime="text/csv", disabled=not nodes
    )
st.caption("The .xlsx/.csv tables are the same edited Objects/Connections data above — open in Excel/Sheets to correct and re-import your own way.")

diagram_snapshot = {
    "saved_at": datetime.now(timezone.utc).isoformat(),
    "source": source,
    "show_labels": show_labels,
    "focus": focus,
    "nodes": [asdict(n) for n in nodes],
    "edges": [asdict(e) for e in edges],
    "findings_by_severity": (
        findings_by_severity(findings) if findings and source == SNAPSHOT_LABEL else None
    ),
    "findings_by_area": (
        findings_by_area(findings) if findings and source == SNAPSHOT_LABEL else None
    ),
}

save_to_library_button(
    {
        "drawio": drawio_xml,
        "gv": gv_source,
        "json": diagram_to_json(nodes, edges),
        "xlsx": xlsx_bytes,
        "csv": csv_text,
    },
    document_type="Architecture Diagram",
    project_name=project_name,
    snapshot=diagram_snapshot,
)
st.caption(
    "Saving also stores a visual snapshot — open this project from the Project Library to see "
    "the diagram, charts, and tables again without re-generating anything."
)
