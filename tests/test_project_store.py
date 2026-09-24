import pytest

from core import project_store


@pytest.fixture()
def tmp_library(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    return tmp_path


def test_save_document_writes_bytes_and_returns_path(tmp_library):
    path = project_store.save_document("Bright Path Wellness", "Written Requirements Document", b"hello", "docx")
    assert path.exists()
    assert path.read_bytes() == b"hello"
    assert path.suffix == ".docx"


def test_save_document_writes_text(tmp_library):
    path = project_store.save_document("Bright Path Wellness", "Test Case Document", "a,b\n1,2", "csv")
    assert path.read_text(encoding="utf-8") == "a,b\n1,2"


def test_save_document_sanitizes_illegal_folder_characters(tmp_library):
    path = project_store.save_document("Client: A/B?", "Doc", b"x", "txt")
    assert ":" not in str(path.relative_to(tmp_library))
    assert "?" not in str(path.relative_to(tmp_library))


def test_list_projects_returns_folders_sorted_case_insensitive(tmp_library):
    project_store.save_document("zeta corp", "Doc", b"x", "txt")
    project_store.save_document("Alpha Inc", "Doc", b"x", "txt")
    assert project_store.list_projects() == ["Alpha Inc", "zeta corp"]


def test_list_projects_empty_when_library_missing(tmp_library):
    assert project_store.list_projects() == []


def test_list_documents_returns_saved_files_newest_first(tmp_library):
    project_store.save_document("Acme", "WRD", b"v1", "docx")
    project_store.save_document("Acme", "WRD", b"v2", "docx")
    docs = project_store.list_documents("Acme")
    assert len(docs) == 2
    assert docs[0].saved_at >= docs[1].saved_at
    assert {d.document_type for d in docs} == {"WRD"}


def test_list_documents_empty_for_unknown_project(tmp_library):
    assert project_store.list_documents("Nonexistent") == []


def test_delete_document_removes_file(tmp_library):
    path = project_store.save_document("Acme", "WRD", b"v1", "docx")
    project_store.delete_document(path)
    assert not path.exists()


def test_delete_document_refuses_path_outside_library(tmp_path, tmp_library):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("nope")
    try:
        with pytest.raises(ValueError):
            project_store.delete_document(outside)
    finally:
        outside.unlink(missing_ok=True)


def test_human_size_formats_reasonably():
    assert project_store.human_size(500) == "500 B"
    assert project_store.human_size(2048) == "2.0 KB"


def test_save_snapshot_then_load_snapshot_round_trips(tmp_library):
    data = {"nodes": [{"name": "Contact"}], "edges": [], "source": "Live portal snapshot"}
    project_store.save_snapshot("Acme", "Architecture Diagram", data)
    loaded = project_store.load_snapshot("Acme", "Architecture Diagram")
    assert loaded == data


def test_save_snapshot_overwrites_rather_than_versions(tmp_library):
    project_store.save_snapshot("Acme", "Architecture Diagram", {"nodes": [{"name": "First"}], "edges": []})
    project_store.save_snapshot("Acme", "Architecture Diagram", {"nodes": [{"name": "Second"}], "edges": []})
    loaded = project_store.load_snapshot("Acme", "Architecture Diagram")
    assert loaded["nodes"] == [{"name": "Second"}]


def test_load_snapshot_returns_none_when_missing(tmp_library):
    assert project_store.load_snapshot("Nonexistent", "Architecture Diagram") is None


def test_list_snapshot_types_reflects_saved_snapshots(tmp_library):
    assert project_store.list_snapshot_types("Acme") == []
    project_store.save_snapshot("Acme", "Architecture Diagram", {"nodes": [], "edges": []})
    assert project_store.list_snapshot_types("Acme") == ["Architecture Diagram"]


def test_list_documents_excludes_the_snapshots_folder(tmp_library):
    project_store.save_document("Acme", "Architecture Diagram", b"x", "json")
    project_store.save_snapshot("Acme", "Architecture Diagram", {"nodes": [], "edges": []})
    docs = project_store.list_documents("Acme")
    assert {d.document_type for d in docs} == {"Architecture Diagram"}
    assert all(d.document_type != "_snapshots" for d in docs)
