"""Smoke tests for the new pages (Modules 5-9) via Streamlit's AppTest
harness: each page must at least render without raising, and the two new
cross-cutting mechanisms -- the WRD-to-Test-Case-Document prefill, and
the "Save to Project Library" button end-to-end (real docx/xlsx/csv/pdf
generation against a page's actual constructed sections) -- are exercised
directly rather than only through the isolated unit tests in
test_exporters.py / test_project_store.py.

Modules 1-4 aren't loaded standalone (via `_run`) here: with no data
pulled yet they hit `st.page_link`, which needs a real page registry to
resolve against and raises when a page script is loaded in isolation.
`test_router_can_reach_every_page` below covers them instead, by going
through the real entrypoint (``Home.py``) the app actually runs under --
see that test's docstring.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent

from core.blueprint import BlueprintGenerator
from core.models import (
    AssociationDef,
    BlueprintInput,
    Finding,
    ObjectSchema,
    PortalPropertyDef,
    PortalSnapshot,
)
from core.project_store import list_documents
from rules.engine import RulesEngine

PAGES_DIR = Path(__file__).resolve().parent.parent / "app_pages"


def _run(page_name: str, *, timeout: float | None = None, **session_state) -> AppTest:
    at = AppTest.from_file(str(PAGES_DIR / page_name))
    for key, value in session_state.items():
        at.session_state[key] = value
    at.run(timeout=timeout)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _diagram_fixtures():
    blueprint = BlueprintGenerator(RulesEngine()).generate(BlueprintInput(project_name="Acme", standard_objects=["Contact"]))
    contact = ObjectSchema(
        object_type="contacts",
        label="Contact",
        is_custom=False,
        properties=[PortalPropertyDef(name="email", label="Email", type="string", hubspot_defined=True)],
    )
    membership = ObjectSchema(
        object_type="2-999",
        label="Membership",
        is_custom=True,
        properties=[],
        associations=[AssociationDef(from_object="Membership", to_object="0-1", label="to Contact", cardinality="")],
    )
    snapshot = PortalSnapshot(pulled_at="2026-01-01T00:00:00+00:00", object_schemas=[contact, membership])
    findings = [Finding(area="Naming", object_type="Membership", description="drift", severity="High", recommended_fix="fix")]
    return blueprint, snapshot, findings


def test_architecture_diagram_page_renders_with_blueprint_and_snapshot():
    blueprint, snapshot, findings = _diagram_fixtures()
    # Generous timeout: this page's PNG export pulls in matplotlib, whose
    # first import in a process (building its font cache) can take a few
    # seconds -- a real one-time cost, not a hang, so it needs more room
    # than the harness's default 3s rather than the page avoiding the work.
    _run(
        "5_Architecture_Diagram.py",
        timeout=20,
        blueprint=blueprint,
        portal_snapshot=snapshot,
        audit_findings=findings,
    )


def test_architecture_diagram_save_to_library_saves_snapshot_visible_in_library(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    from core import project_store

    blueprint, snapshot, findings = _diagram_fixtures()
    at = _run(
        "5_Architecture_Diagram.py",
        timeout=20,
        blueprint=blueprint,
        portal_snapshot=snapshot,
        audit_findings=findings,
        report_project_name="Acme Corp",
    )

    save_buttons = [b for b in at.button if b.label == "Save to Project Library"]
    assert save_buttons, "expected a Save to Project Library button"
    at = save_buttons[0].click().run(timeout=20)
    assert not at.exception, [str(e) for e in at.exception]

    assert project_store.list_snapshot_types("Acme Corp") == ["Architecture Diagram"]
    saved = project_store.load_snapshot("Acme Corp", "Architecture Diagram")
    assert saved["nodes"], "expected the saved snapshot to include the diagram's nodes"

    lib_at = _run("9_Project_Library.py")
    subheaders = [el.value for el in lib_at.subheader]
    assert "Visual preview" in subheaders
    assert not lib_at.exception, [str(e) for e in lib_at.exception]


def test_architecture_diagram_empty_state_offers_saved_project_picker(monkeypatch, tmp_path):
    """A fresh session with nothing generated yet ('Nothing to diagram yet')
    must still offer a way to pull up a project saved in an earlier
    session, rather than only linking to the generator pages. Goes through
    the real router (Home.py + switch_page), not a standalone page load --
    this branch hits st.page_link, which needs a real page registry (see
    the module docstring)."""
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    from core import project_store

    blueprint, snapshot, findings = _diagram_fixtures()
    setup = AppTest.from_file(str(REPO_ROOT / "Home.py"))
    setup.run(timeout=20)
    setup.switch_page("app_pages/5_Architecture_Diagram.py")
    setup.session_state["blueprint"] = blueprint
    setup.session_state["portal_snapshot"] = snapshot
    setup.session_state["audit_findings"] = findings
    setup.session_state["report_project_name"] = "Acme Corp"
    setup.run(timeout=20)
    assert not setup.exception, [str(e) for e in setup.exception]
    save_buttons = [b for b in setup.button if b.label == "Save to Project Library"]
    setup = save_buttons[0].click().run(timeout=20)
    assert not setup.exception, [str(e) for e in setup.exception]
    assert project_store.list_snapshot_types("Acme Corp") == ["Architecture Diagram"]

    # Fresh session, nothing in st.session_state -- the exact empty state from the screenshot.
    at = AppTest.from_file(str(REPO_ROOT / "Home.py"))
    at.run(timeout=20)
    at.switch_page("app_pages/5_Architecture_Diagram.py")
    at.run(timeout=20)
    assert not at.exception, [str(e) for e in at.exception]

    expanders = [e.label for e in at.expander]
    assert "View a previously saved diagram" in expanders
    pickers = [s for s in at.selectbox if s.label == "Project"]
    assert pickers and "Acme Corp" in pickers[0].options

    at = pickers[0].select("Acme Corp").run(timeout=20)
    assert not at.exception, [str(e) for e in at.exception]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics.get("Objects") == "2"


def test_requirements_document_page_renders_with_no_state():
    _run("6_Requirements_Document.py")


def test_joint_evaluation_plan_page_renders_with_no_state():
    _run("7_Joint_Evaluation_Plan.py")


def test_test_case_document_page_renders_with_no_state():
    _run("8_Test_Case_Document.py")


def test_project_library_page_renders_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    _run("9_Project_Library.py")


def test_project_library_page_lists_a_saved_document(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    from core import project_store

    project_store.save_document("Acme Corp", "Written Requirements Document", b"hello", "docx")
    at = _run("9_Project_Library.py")
    assert "Acme Corp" in at.selectbox[0].options
    assert at.expander[0].label.startswith("Written Requirements Document")


def test_wrd_save_to_library_generates_all_four_formats(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    at = _run("6_Requirements_Document.py", wrd_project_name="Acme Corp")

    save_buttons = [b for b in at.button if b.label == "Save to Project Library"]
    assert save_buttons, "expected a Save to Project Library button"
    at = save_buttons[0].click().run()
    assert not at.exception, [str(e) for e in at.exception]

    docs = list_documents("Acme Corp")
    assert {d.filename.rsplit(".", 1)[-1] for d in docs} == {"docx", "xlsx", "csv", "pdf"}


def test_test_case_document_loads_requirements_from_wrd_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_LIBRARY_DIR", str(tmp_path))
    wrd_requirements = [{"Requirement": "Sync contacts nightly"}, {"Requirement": "Log SMS replies"}]
    at = _run("8_Test_Case_Document.py", wrd_requirements_snapshot=wrd_requirements)

    load_buttons = [b for b in at.button if "Load requirements" in b.label]
    assert load_buttons and not load_buttons[0].disabled
    at = load_buttons[0].click().run()
    assert not at.exception, [str(e) for e in at.exception]

    seed = at.session_state["tcd_rows_seed"]
    assert any("Sync contacts nightly" in row["Requirement"] for row in seed)
    assert any("Log SMS replies" in row["Requirement"] for row in seed)


def test_property_audit_page_renders_with_no_state():
    _run("2b_Property_Audit.py")


# ---- Home.py router -----------------------------------------------------------
#
# Home.py is the actual Streamlit entrypoint: it declares every page via
# st.Page/st.navigation and groups them into sidebar sections (Architecture &
# Planning / Auditing / Documentation / Library). Loading it directly, rather
# than an individual page file, is also the only way to exercise pages that
# call st.page_link (Modules 1-4's landing/cross-links) — a bare page script
# loaded in isolation has no page registry for those links to resolve
# against and raises, but going through the router gives it one.


def test_router_renders_default_landing_page():
    at = AppTest.from_file(str(REPO_ROOT / "Home.py"))
    at.run(timeout=20)
    assert not at.exception, [str(e) for e in at.exception]
    assert len(at.markdown) > 0


def test_router_can_reach_every_page():
    for page_path in sorted((REPO_ROOT / "app_pages").glob("*.py")):
        at = AppTest.from_file(str(REPO_ROOT / "Home.py"))
        at.run(timeout=20)
        at.switch_page(f"app_pages/{page_path.name}")
        at.run(timeout=20)
        assert not at.exception, f"{page_path.name}: {[str(e) for e in at.exception]}"
