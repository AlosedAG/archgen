"""Streamlit-coupled rendering for the "download this / save this to the
project library" footer every document-producing page ends with.

Kept separate from ``archscope_domain.exporters`` so the actual format-conversion
logic stays pure-Python and unit-testable without a Streamlit runtime;
this module is the thin, untested-by-design UI glue on top of it.
"""

from __future__ import annotations

import streamlit as st

from core import project_store
from archscope_domain.exporters import Section, sections_to_csv, sections_to_docx, sections_to_pdf, sections_to_xlsx

_DOWNLOAD_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
    "json": "application/json",
    "md": "text/markdown",
}


def render_sections_export(
    doc_title: str,
    subtitle: str,
    sections: list[Section],
    *,
    document_type: str,
    project_name: str,
    file_stub: str,
    snapshot: dict | None = None,
) -> None:
    """Full docx/xlsx/csv/pdf export row + a "Save to Project Library"
    button, built directly from ``sections``. Use for the note-taking
    modules (WRD, JEP, Test Case Document)."""
    artifacts: dict[str, bytes | str] = {
        "docx": sections_to_docx(doc_title, subtitle, sections).getvalue(),
        "xlsx": sections_to_xlsx(sections),
        "csv": sections_to_csv(sections),
        "pdf": sections_to_pdf(doc_title, subtitle, sections),
    }
    render_export_footer(
        artifacts, document_type=document_type, project_name=project_name, file_stub=file_stub, snapshot=snapshot
    )


def render_export_footer(
    artifacts: dict[str, bytes | str],
    *,
    document_type: str,
    project_name: str,
    file_stub: str,
    snapshot: dict | None = None,
) -> None:
    """Download buttons (one per key in ``artifacts``) plus a "Save to
    Project Library" button that writes every artifact to disk under
    ``project_name`` / ``document_type`` with a shared timestamp. Use
    directly when a page already has its export bytes/strings in hand in
    formats other than the standard four (e.g. Module 1's .md/.json).

    ``snapshot``, when given, is also saved (see ``save_to_library_button``)
    so the Project Library page can redraw this page's own charts/tables/
    diagram later instead of only offering these files for download."""
    st.divider()
    st.subheader("Export")

    cols = st.columns(len(artifacts))
    for col, (ext, content) in zip(cols, artifacts.items()):
        with col:
            st.download_button(
                f"Download .{ext}",
                data=content,
                file_name=f"{file_stub}.{ext}",
                mime=_DOWNLOAD_MIME.get(ext, "application/octet-stream"),
            )
    st.caption(
        "Every format above is fully editable afterward — .docx and .xlsx open directly in "
        "Word/Excel (or Google Docs/Sheets) for corrections."
    )
    save_to_library_button(artifacts, document_type=document_type, project_name=project_name, snapshot=snapshot)


def save_to_library_button(
    artifacts: dict[str, bytes | str],
    *,
    document_type: str,
    project_name: str,
    snapshot: dict | None = None,
) -> None:
    """Just the "Save to Project Library" button (no download buttons) —
    for pages that already render their own download buttons and only
    need the library-saving action added alongside them.

    ``snapshot``, when given, is a JSON-serializable dict of whatever this
    page needs to redraw its own visuals later (e.g. the Architecture
    Diagram's node/edge lists and finding counts) — saved alongside the
    downloadable files so the Project Library page can show a live preview
    of this project instead of only raw files to download."""
    project_name = (project_name or "").strip()
    if st.button("Save to Project Library", type="primary", disabled=not project_name, key=f"save_{document_type}"):
        for ext, content in artifacts.items():
            project_store.save_document(project_name, document_type, content, ext)
        if snapshot is not None:
            project_store.save_snapshot(project_name, document_type, snapshot)
        st.success(f"Saved to the project library under “{project_name}” / {document_type}.")
    if not project_name:
        st.caption("Enter a project name above to enable saving to the project library.")
