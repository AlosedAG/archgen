"""Filesystem-backed project library.

Every module in this app can save its generated output here, grouped by
project name and tagged with a generation timestamp, so a user can come
back later and find everything produced for a given project without
re-running anything. Pure local files, no database — consistent with the
rest of the app only ever touching HubSpot (read-only) and the local
filesystem.

Layout: ``<library_root()>/<project name>/<document type>/
<document type>_<YYYY-MM-DD_HHMMSS>.<ext>``. Folder names are the project
name / document type with filesystem-illegal characters swapped out —
kept human-readable rather than slugified, so the folder you see on disk
is the folder you'd expect from the name you typed.

A separate ``<project name>/_snapshots/<document type>.json`` holds, for
pages that opt in, enough structured data to redraw that page's own
charts/tables/diagram later (see :func:`save_snapshot`) — one current
snapshot per document type, not a version history — so the Project
Library page can show a visual preview of a project instead of only
offering its exported files for download.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "project_library"

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TIMESTAMP_RE = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{6}_\d{3})\.")

# Reserved subfolder name for save_snapshot()/load_snapshot() below -- kept
# out of list_documents()/list_projects()'s document-type listing so it
# never shows up as a fake "_snapshots" document type in the file browser.
_SNAPSHOTS_DIRNAME = "_snapshots"


def library_root() -> Path:
    override = os.environ.get("PROJECT_LIBRARY_DIR")
    return Path(override) if override else DEFAULT_LIBRARY_DIR


def safe_foldername(name: str) -> str:
    cleaned = _ILLEGAL_CHARS.sub("_", name or "").strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Untitled"


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


@dataclass
class SavedDocument:
    project_folder: str
    document_type: str
    filename: str
    path: Path
    saved_at: datetime
    size_bytes: int


def save_document(project_name: str, document_type: str, content: bytes | str, extension: str) -> Path:
    project_dir = library_root() / safe_foldername(project_name)
    type_dir = project_dir / safe_foldername(document_type)
    type_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    # Millisecond precision: two saves in the same module (e.g. re-saving
    # after a quick edit) can otherwise land in the same second and
    # silently overwrite each other.
    timestamp = f"{now.strftime('%Y-%m-%d_%H%M%S')}_{now.microsecond // 1000:03d}"
    ext = extension.lstrip(".")
    filename = f"{safe_foldername(document_type)}_{timestamp}.{ext}"
    path = type_dir / filename

    if isinstance(content, (bytes, bytearray)):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def save_snapshot(project_name: str, document_type: str, data: dict) -> Path:
    """Save a JSON snapshot of a page's current visual state — whatever a
    page needs to redraw its own charts/tables/diagram later (e.g. the
    Architecture Diagram's node/edge lists and finding counts) — so the
    Project Library can reconstruct that view instead of only offering the
    exported files for download.

    Unlike :func:`save_document`, this is a single file per (project,
    document_type): saving again overwrites it. A snapshot is "what this
    page currently looks like for this project," not a version history —
    the timestamped files from :func:`save_document` already cover that.
    """
    snap_dir = library_root() / safe_foldername(project_name) / _SNAPSHOTS_DIRNAME
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = snap_dir / f"{safe_foldername(document_type)}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def load_snapshot(project_folder: str, document_type: str) -> Optional[dict]:
    """Load a snapshot saved by :func:`save_snapshot`, or ``None`` if this
    project has no saved snapshot for that document type (either nothing
    was ever saved, or it predates this feature)."""
    path = library_root() / project_folder / _SNAPSHOTS_DIRNAME / f"{safe_foldername(document_type)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_snapshot_types(project_folder: str) -> list[str]:
    """Document types with a saved visual snapshot for this project, e.g.
    ``["Architecture Diagram"]`` — drives which "visual preview" sections
    the Project Library page renders for a selected project."""
    snap_dir = library_root() / project_folder / _SNAPSHOTS_DIRNAME
    if not snap_dir.exists():
        return []
    return sorted(p.stem for p in snap_dir.glob("*.json"))


def list_projects() -> list[str]:
    root = library_root()
    if not root.exists():
        return []
    return sorted((p.name for p in root.iterdir() if p.is_dir()), key=str.lower)


def _parse_saved_at(file_path: Path) -> datetime:
    match = _TIMESTAMP_RE.search(file_path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S_%f")
        except ValueError:
            pass
    return datetime.fromtimestamp(file_path.stat().st_mtime)


def list_documents(project_folder: str) -> list[SavedDocument]:
    project_dir = library_root() / project_folder
    if not project_dir.exists():
        return []
    documents: list[SavedDocument] = []
    type_dirs = (p for p in project_dir.iterdir() if p.is_dir() and p.name != _SNAPSHOTS_DIRNAME)
    for type_dir in sorted(type_dirs, key=lambda p: p.name.lower()):
        for file_path in type_dir.iterdir():
            if not file_path.is_file():
                continue
            documents.append(
                SavedDocument(
                    project_folder=project_folder,
                    document_type=type_dir.name,
                    filename=file_path.name,
                    path=file_path,
                    saved_at=_parse_saved_at(file_path),
                    size_bytes=file_path.stat().st_size,
                )
            )
    documents.sort(key=lambda d: d.saved_at, reverse=True)
    return documents


def delete_document(path: Path) -> None:
    root = library_root().resolve()
    resolved = Path(path).resolve()
    if root not in resolved.parents:
        raise ValueError("Refusing to delete a path outside the project library.")
    resolved.unlink(missing_ok=True)


def project_name_input(
    label: str = "Project name (for saving to the library)", key: str = "report_project_name"
) -> str:
    """Shared project-name text input: same session_state key across
    pages, so a name typed on one page carries over to the others, with
    :func:`guess_project_name` as the first page's starting guess."""
    import streamlit as st

    st.session_state.setdefault(key, guess_project_name())
    return st.text_input(label, key=key)


def guess_project_name() -> str:
    """Best-effort default for a project-name field, pulled from whatever
    other module output already sits in session state. Purely a UI
    convenience — every page using this still shows an editable text
    input, so a missing/wrong guess costs nothing."""
    import streamlit as st

    blueprint = st.session_state.get("blueprint")
    if blueprint is not None and getattr(blueprint, "project_name", ""):
        return blueprint.project_name
    for key in ("wrd_project_name", "jep_project_name", "report_project_name"):
        value = st.session_state.get(key)
        if value:
            return value
    return ""
