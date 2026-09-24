"""Module 9 — Project Library.

Every module's "Save to Project Library" button writes here: a plain
folder-per-project, folder-per-document-type layout on local disk, so
everything generated for a project — requirements docs, blueprints,
audits, diagrams, reports — is in one place with the date each file was
generated, independent of this browser session.

Reads nothing from ``st.session_state`` — purely a browser over what's
already saved to disk. Pages that also save a visual snapshot (currently
just the Architecture Diagram — see ``core.project_store.save_snapshot``)
get an inline "Visual preview" section here too: the actual diagram/
charts/tables reconstructed from that snapshot, so selecting a project is
enough to see what was done, not just a list of files to download.
"""

from __future__ import annotations

import streamlit as st

from core import project_store
from core.diagram_preview import render_diagram_snapshot
from core.theme import inject_global_css, render_page_header

st.set_page_config(page_title="Project Library", layout="wide")
inject_global_css()
render_page_header(
    "Project Library",
    "Everything saved from every module, organized by project and document type, with the date "
    "each file was generated.",
)

st.caption(f"Library location: `{project_store.library_root()}`")

projects = project_store.list_projects()
if not projects:
    st.info("Nothing saved yet. Every module has a 'Save to Project Library' button next to its downloads.")
    st.stop()

project = st.selectbox("Project", projects)

_PREVIEW_RENDERERS = {
    "Architecture Diagram": render_diagram_snapshot,
}

snapshot_types = [t for t in project_store.list_snapshot_types(project) if t in _PREVIEW_RENDERERS]
if snapshot_types:
    st.divider()
    st.subheader("Visual preview")
    for doc_type in snapshot_types:
        data = project_store.load_snapshot(project, doc_type)
        if not data:
            continue
        st.markdown(f"**{doc_type}**")
        _PREVIEW_RENDERERS[doc_type](data)

documents = project_store.list_documents(project)

if not documents:
    st.info("No documents saved for this project yet.")
    st.stop()

st.divider()
st.subheader("Saved files")
st.caption(f"{len(documents)} file(s) across {len({d.document_type for d in documents})} document type(s).")

document_types = sorted({d.document_type for d in documents})
for doc_type in document_types:
    type_docs = [d for d in documents if d.document_type == doc_type]
    with st.expander(f"{doc_type} ({len(type_docs)})", expanded=True):
        header = st.columns([3, 2, 1, 1, 1])
        for col, label in zip(header, ["File", "Generated", "Size", "", ""]):
            col.markdown(f"**{label}**")
        for doc in type_docs:
            col_name, col_date, col_size, col_dl, col_del = st.columns([3, 2, 1, 1, 1])
            col_name.write(doc.filename)
            col_date.write(doc.saved_at.strftime("%Y-%m-%d %H:%M"))
            col_size.write(project_store.human_size(doc.size_bytes))
            with col_dl:
                st.download_button("Download", data=doc.path.read_bytes(), file_name=doc.filename, key=f"dl_{doc.path}")
            with col_del:
                if st.button("Delete", key=f"del_{doc.path}"):
                    project_store.delete_document(doc.path)
                    st.rerun()
