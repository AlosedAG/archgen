import json
import xml.etree.ElementTree as ET

import pytest

from core.diagram import (
    DiagramEdge,
    DiagramNode,
    dangling_edges,
    dedupe_edges,
    diagram_to_json,
    findings_by_area,
    findings_by_severity,
    from_blueprint,
    from_snapshot,
    to_drawio_xml,
    to_graphviz,
    to_png_bytes,
)
from core.models import (
    AssociationDef,
    Blueprint,
    BlueprintInput,
    CustomObjectDef,
    Finding,
    ObjectSchema,
    PortalSnapshot,
    PropertyDef,
)


@pytest.fixture()
def blueprint() -> Blueprint:
    return Blueprint(
        project_name="Test Project",
        generated_at="2026-01-01T00:00:00+00:00",
        inputs=BlueprintInput(standard_objects=["Contact", "Deal"]),
        custom_objects=[
            CustomObjectDef(
                name="Membership",
                plural_label="Memberships",
                description="Tracks a membership term.",
                properties=[PropertyDef(name="membership_status", label="Membership Status", type="enumeration")],
            )
        ],
        standard_object_properties={
            "Contact": [PropertyDef(name="lifecyclestage", label="Lifecycle Stage", type="enumeration")],
            "Deal": [],
        },
        associations=[
            AssociationDef(from_object="Membership", to_object="Contact", label="Membership to Contact", cardinality="many-to-one"),
            AssociationDef(from_object="Membership", to_object="Company", label="Membership to Company", cardinality="many-to-one"),
        ],
    )


@pytest.fixture()
def snapshot() -> PortalSnapshot:
    contact = ObjectSchema(object_type="contacts", label="Contact", is_custom=False, properties=[])
    deal = ObjectSchema(object_type="deals", label="Deal", is_custom=False, properties=[])
    membership = ObjectSchema(
        object_type="2-999",
        label="Membership",
        is_custom=True,
        properties=[],
        associations=[
            AssociationDef(from_object="Membership", to_object="0-1", label="Membership to Contact", cardinality=""),
            AssociationDef(from_object="Membership", to_object="0-27", label="Membership to Task", cardinality=""),
        ],
    )
    return PortalSnapshot(pulled_at="2026-01-01T00:00:00+00:00", object_schemas=[contact, deal, membership])


@pytest.fixture()
def findings() -> list[Finding]:
    return [
        Finding(area="Naming", object_type="Membership", description="drift", severity="High", recommended_fix="fix"),
        Finding(area="Records", object_type="Membership", description="missing data", severity="Low", recommended_fix="fix"),
        Finding(area="Permissions", object_type="Owner", description="unassigned", severity="Medium", recommended_fix="fix"),
    ]


# ---- builders ---------------------------------------------------------------


def test_from_blueprint_builds_nodes_for_standard_and_custom_objects(blueprint):
    nodes, edges = from_blueprint(blueprint)
    by_name = {n.name: n for n in nodes}
    assert by_name["Contact"].kind == "Standard"
    assert by_name["Membership"].kind == "Custom"
    assert by_name["Membership"].property_count == 1
    assert len(edges) == 2


def test_from_blueprint_adds_dangling_association_targets_as_nodes(blueprint):
    # "Company" is never a standard/custom object in this blueprint, only an
    # association target -- it should still show up so the edge isn't dropped.
    nodes, _ = from_blueprint(blueprint)
    names = {n.name for n in nodes}
    assert "Company" in names
    assert next(n for n in nodes if n.name == "Company").kind == "Standard"


def test_from_snapshot_resolves_type_ids_and_attaches_findings(snapshot, findings):
    nodes, edges = from_snapshot(snapshot, findings)
    by_name = {n.name: n for n in nodes}
    assert by_name["Membership"].risk == "High"
    assert by_name["Membership"].finding_count == 2
    assert by_name["Contact"].risk == ""
    assert edges == [DiagramEdge(source="Membership", target="Contact", label="Membership to Contact", cardinality="")]


def test_from_snapshot_without_findings_has_no_risk(snapshot):
    nodes, _ = from_snapshot(snapshot, None)
    assert all(n.risk == "" for n in nodes)


def test_from_snapshot_excludes_engagement_associations_by_default(snapshot):
    # A real portal declares an association from nearly every object to
    # HubSpot's generic engagement types (Task, Note, Email, ...) -- these
    # aren't part of the client's own data model and mostly add clutter,
    # so they're off unless explicitly requested.
    nodes, edges = from_snapshot(snapshot)
    names = {n.name for n in nodes}
    assert "Task" not in names
    assert not any(e.target == "Task" for e in edges)


def test_from_snapshot_includes_engagements_when_requested(snapshot):
    nodes, edges = from_snapshot(snapshot, include_engagements=True)
    by_name = {n.name: n for n in nodes}
    assert by_name["Task"].kind == "Activity"
    assert any(e.source == "Membership" and e.target == "Task" for e in edges)


# ---- edge deduplication -----------------------------------------------------


def test_dedupe_edges_merges_labels_for_duplicate_source_target_pairs():
    edges = [
        DiagramEdge(source="Children", target="Families", label="children_to_families", cardinality="many-to-one"),
        DiagramEdge(source="Children", target="Families", label="primary_guardian", cardinality="many-to-one"),
    ]
    result = dedupe_edges(edges)
    assert len(result) == 1
    assert result[0].label == "children_to_families; primary_guardian"


def test_dedupe_edges_keeps_distinct_pairs_separate():
    edges = [DiagramEdge(source="A", target="B"), DiagramEdge(source="B", target="A")]
    assert len(dedupe_edges(edges)) == 2


def test_dedupe_edges_blanks_cardinality_when_sources_disagree():
    edges = [
        DiagramEdge(source="A", target="B", cardinality="one-to-many"),
        DiagramEdge(source="A", target="B", cardinality="many-to-many"),
    ]
    assert dedupe_edges(edges)[0].cardinality == ""


# ---- chart helpers ------------------------------------------------------------


def test_findings_by_severity_counts(findings):
    counts = findings_by_severity(findings)
    assert counts == {"High": 1, "Medium": 1, "Low": 1}


def test_findings_by_area_counts(findings):
    counts = findings_by_area(findings)
    assert counts == {"Naming": 1, "Records": 1, "Permissions": 1}


# ---- rendering ------------------------------------------------------------


def test_to_graphviz_includes_node_and_edge_labels():
    nodes = [DiagramNode(name="Contact"), DiagramNode(name="Membership", kind="Custom", risk="High", finding_count=2)]
    edges = [DiagramEdge(source="Membership", target="Contact", label="Membership to Contact")]
    dot = to_graphviz(nodes, edges)
    assert dot.startswith("digraph architecture {")
    assert '"Contact"' in dot
    assert '"Membership"' in dot
    assert "Membership to Contact" in dot


def test_to_graphviz_skips_dangling_edges():
    nodes = [DiagramNode(name="Contact")]
    edges = [DiagramEdge(source="Contact", target="Ghost", label="broken")]
    dot = to_graphviz(nodes, edges)
    assert "Ghost" not in dot


def test_to_graphviz_escapes_quotes_in_names():
    nodes = [DiagramNode(name='Weird "Object"')]
    dot = to_graphviz(nodes, [])
    assert '\\"Object\\"' in dot


def test_to_graphviz_node_subtitle_uses_a_real_dot_newline_escape():
    # Regression: escaping the name+subtitle as one already-joined string
    # doubled the backslash in the "\n" line-break escape, so Graphviz
    # printed a literal "\n" in the rendered label instead of breaking the
    # line -- name and subtitle must be escaped independently and joined
    # with a single, un-escaped "\n" afterward.
    dot = to_graphviz([DiagramNode(name="Contact", property_count=1)], [])
    assert 'label="Contact\\n1 property"' in dot
    assert "\\\\n" not in dot


def test_to_graphviz_activity_node_with_no_data_has_no_subtitle_line():
    dot = to_graphviz([DiagramNode(name="Task", kind="Activity")], [])
    assert 'label="Task"' in dot
    assert "0 properties" not in dot


def test_to_graphviz_condenses_merged_edge_labels():
    nodes = [DiagramNode(name="A"), DiagramNode(name="B")]
    edges = [DiagramEdge(source="A", target="B", label="first; second; third")]
    dot = to_graphviz(nodes, edges)
    assert "first (+2)" in dot
    assert "second" not in dot


def test_to_graphviz_can_hide_edge_labels():
    nodes = [DiagramNode(name="A"), DiagramNode(name="B")]
    edges = [DiagramEdge(source="A", target="B", label="link")]
    dot = to_graphviz(nodes, edges, show_labels=False)
    assert '"A" -> "B";' in dot
    assert "link" not in dot


def test_dangling_edges_reports_unmatched_endpoints():
    nodes = [DiagramNode(name="Contact")]
    edges = [
        DiagramEdge(source="Contact", target="Membership"),
        DiagramEdge(source="Ghost", target="Contact"),
    ]
    result = dangling_edges(nodes, edges)
    assert len(result) == 2


# ---- exporters -------------------------------------------------------------


def test_diagram_to_json_round_trips():
    nodes = [DiagramNode(name="Contact", kind="Standard")]
    edges = [DiagramEdge(source="Contact", target="Membership", label="link")]
    parsed = json.loads(diagram_to_json(nodes, edges))
    assert parsed["nodes"][0]["name"] == "Contact"
    assert parsed["edges"][0]["target"] == "Membership"


def test_to_drawio_xml_is_well_formed_and_contains_node_values():
    nodes = [DiagramNode(name="Contact"), DiagramNode(name="Membership", kind="Custom", risk="Medium", finding_count=1)]
    edges = [DiagramEdge(source="Membership", target="Contact", label="Membership to Contact")]
    xml_str = to_drawio_xml(nodes, edges)
    root = ET.fromstring(xml_str)
    assert root.tag == "mxfile"
    values = [cell.get("value") for cell in root.iter("mxCell") if cell.get("value")]
    assert any("Contact" in v for v in values)
    assert any("Membership" in v for v in values)


def test_to_drawio_xml_skips_dangling_edges():
    nodes = [DiagramNode(name="Contact")]
    edges = [DiagramEdge(source="Contact", target="Ghost")]
    xml_str = to_drawio_xml(nodes, edges)
    root = ET.fromstring(xml_str)
    edge_cells = [cell for cell in root.iter("mxCell") if cell.get("edge") == "1"]
    assert edge_cells == []


def test_to_drawio_xml_dedupes_parallel_edges():
    nodes = [DiagramNode(name="Children"), DiagramNode(name="Families")]
    edges = [
        DiagramEdge(source="Children", target="Families", label="children_to_families"),
        DiagramEdge(source="Children", target="Families", label="primary_guardian"),
    ]
    xml_str = to_drawio_xml(nodes, edges)
    root = ET.fromstring(xml_str)
    edge_cells = [cell for cell in root.iter("mxCell") if cell.get("edge") == "1"]
    assert len(edge_cells) == 1


def test_to_drawio_xml_groups_nodes_by_kind_most_connected_first():
    # Standard objects should be laid out before Custom, and within a kind
    # the most-connected node should come first -- so a hub object doesn't
    # land on the opposite side of the canvas from most of its edges.
    nodes = [
        DiagramNode(name="Quiet", kind="Custom"),
        DiagramNode(name="Hub", kind="Custom"),
        DiagramNode(name="Contact", kind="Standard"),
    ]
    edges = [
        DiagramEdge(source="Hub", target="Contact"),
        DiagramEdge(source="Hub", target="Quiet"),
    ]
    xml_str = to_drawio_xml(nodes, edges)
    root = ET.fromstring(xml_str)
    vertices = [c for c in root.iter("mxCell") if c.get("vertex") == "1"]
    # ElementTree decodes the "&lt;br&gt;" entities back to a literal "<br>"
    # when parsing the attribute value.
    order = [c.get("value").split("<br>")[0] for c in vertices]
    assert order.index("Contact") < order.index("Hub") < order.index("Quiet")


def test_to_drawio_xml_can_hide_edge_labels():
    nodes = [DiagramNode(name="A"), DiagramNode(name="B")]
    edges = [DiagramEdge(source="A", target="B", label="link")]
    xml_str = to_drawio_xml(nodes, edges, show_labels=False)
    root = ET.fromstring(xml_str)
    edge_cell = next(c for c in root.iter("mxCell") if c.get("edge") == "1")
    assert edge_cell.get("value") == ""


def test_to_drawio_xml_sizes_nodes_to_fit_a_long_label():
    # The old layout used a flat 200x70 box for every node regardless of
    # label length, so a long name/subtitle would overflow or clip.
    long_name = "A Very Long Custom Object Name That Would Overflow A Fixed Box"
    nodes = [DiagramNode(name=long_name, kind="Custom", property_count=12)]
    xml_str = to_drawio_xml(nodes, [])
    root = ET.fromstring(xml_str)
    vertex = next(c for c in root.iter("mxCell") if c.get("vertex") == "1")
    geometry = vertex.find("mxGeometry")
    assert float(geometry.get("height")) > 70


def test_to_drawio_xml_routes_around_a_band_it_skips():
    # Regression: an edge from a Standard object straight to an Activity
    # type skips over the Custom band sitting between them. The old
    # midpoint-only routing drew that edge's line (and label) straight
    # through whatever Custom object happened to be in the middle -- it
    # must now bypass around the row instead of cutting through it.
    nodes = [
        DiagramNode(name="Deal", kind="Standard"),
        DiagramNode(name="Membership", kind="Custom"),
        DiagramNode(name="Task", kind="Activity"),
    ]
    edges = [
        DiagramEdge(source="Deal", target="Membership", label="deal_to_membership"),
        DiagramEdge(source="Deal", target="Task", label="deal_to_task"),
    ]
    xml_str = to_drawio_xml(nodes, edges)
    root = ET.fromstring(xml_str)

    boxes = {}
    for cell in root.iter("mxCell"):
        if cell.get("vertex") == "1":
            name = cell.get("value").split("<br>")[0]
            g = cell.find("mxGeometry")
            boxes[name] = (float(g.get("x")), float(g.get("y")), float(g.get("width")), float(g.get("height")))
    mx, my, mw, mh = boxes["Membership"]

    skip_edge = next(c for c in root.iter("mxCell") if c.get("edge") == "1" and c.get("value") == "deal_to_task")
    waypoints = [(float(p.get("x")), float(p.get("y"))) for p in skip_edge.iter("mxPoint")]
    assert waypoints, "expected explicit routing waypoints on the edge"
    for px, py in waypoints:
        assert not (mx <= px <= mx + mw and my <= py <= my + mh)


# ---- PNG export -------------------------------------------------------------


def test_to_png_bytes_returns_a_valid_png():
    nodes = [DiagramNode(name="Contact"), DiagramNode(name="Membership", kind="Custom")]
    edges = [DiagramEdge(source="Membership", target="Contact", label="link")]
    png_bytes = to_png_bytes(nodes, edges)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 500


def test_to_png_bytes_handles_no_nodes():
    png_bytes = to_png_bytes([], [])
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
