"""Module 5 — Architecture Diagram.

Turns either a generated ``Blueprint`` (Module 1) or a pulled
``PortalSnapshot`` (Module 2/3) — optionally annotated with audit
``Finding`` objects (Module 2) — into a plain, editable node/edge diagram:
an entity-relationship-style view of the objects in scope and how they
connect, color-coded by object kind and by the worst audit finding
attached to each object.

Deliberately built as two flat lists of small dataclasses
(``DiagramNode`` / ``DiagramEdge``) rather than rendered straight off the
source data. ``app_pages/5_Architecture_Diagram.py`` loads them into editable
tables first, so a user can fix something the generator or the audit got
wrong (rename an object, drop a spurious association, correct a
cardinality) before rendering or exporting — the generator/audit output is
a starting point, not the final word on the client's environment.

A live portal typically declares an association from most objects to
HubSpot's generic engagement types (Task, Note, Email, Call, Meeting, ...)
— every portal has these, they aren't part of *this* client's data model,
and on a real portal they can outnumber the objects that actually matter.
They're modeled as their own ``"Activity"`` kind and excluded from
``from_snapshot`` by default (``include_engagements=False``) so the
diagram starts legible; a page-level toggle can bring them back in.

Exports: Graphviz DOT source (opens in any Graphviz viewer/editor), a
diagrams.net / draw.io ``.drawio`` file (free, no-login, full
drag-and-drop editing — the closest open, scriptable equivalent to a
Lucidchart file), and the edited node/edge data as JSON.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Optional
from xml.sax.saxutils import escape

from core.audit import STANDARD_TYPE_ID_LABELS
from core.models import Blueprint, Finding, PortalSnapshot
from core.theme import BG_ALT, BORDER, PURPLE, PURPLE_LIGHT, TEXT_BODY, TEXT_DARK

# Object names this app treats as HubSpot standard objects when it has to
# guess the kind of an association endpoint that isn't in the source's own
# object list (e.g. a custom object associates to "Deal" but "Deal" wasn't
# pulled/selected as an object in scope). Not exhaustive — just enough to
# avoid mislabeling the common cases as "Custom".
_KNOWN_STANDARD_OBJECTS = {"Contact", "Company", "Deal", "Ticket", "Line Item", "Product", "Quote"}

# HubSpot's built-in engagement/activity object type IDs — stable across
# every portal, not specific to any one client (same table as
# core.report's private copy; kept separate here to avoid coupling two
# otherwise-independent modules over ten lines of static data).
_ENGAGEMENT_TYPE_ID_LABELS: dict[str, str] = {
    "0-4": "Engagement",
    "0-18": "Communication",
    "0-27": "Task",
    "0-43": "Task Template",
    "0-46": "Note",
    "0-47": "Meeting",
    "0-48": "Call",
    "0-49": "Email",
    "0-51": "Conversation Session",
    "0-116": "Postal Mail",
}
_ENGAGEMENT_TYPE_IDS = set(_ENGAGEMENT_TYPE_ID_LABELS)

SEVERITY_COLORS: dict[str, str] = {
    "High": "#D64545",
    "Medium": "#F7791D",
    "Low": "#E8B339",
    "": BORDER,
}
_SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "": 3}


@dataclasses.dataclass
class DiagramNode:
    name: str
    kind: str = "Standard"  # "Standard" | "Custom" | "Activity"
    property_count: int = 0
    risk: str = ""  # "" | "Low" | "Medium" | "High" — worst finding severity for this object
    finding_count: int = 0
    notes: str = ""


@dataclasses.dataclass
class DiagramEdge:
    source: str
    target: str
    label: str = ""
    cardinality: str = "many-to-many"


def _worst_severity(severities: list[str]) -> str:
    if not severities:
        return ""
    return min(severities, key=lambda s: _SEVERITY_ORDER.get(s, 3))


def _ensure_endpoints(nodes: dict[str, DiagramNode], edges: list[DiagramEdge]) -> None:
    """Add a placeholder node for any edge endpoint not already modeled, so a
    dangling association still shows up on the diagram instead of being
    silently dropped."""
    for e in edges:
        for name in (e.source, e.target):
            if name and name not in nodes:
                kind = "Standard" if name in _KNOWN_STANDARD_OBJECTS else "Custom"
                nodes[name] = DiagramNode(name=name, kind=kind)


def dedupe_edges(edges: list[DiagramEdge]) -> list[DiagramEdge]:
    """Collapse multiple association definitions between the same pair of
    objects (a real, common case — e.g. two differently-labeled
    association types between the same two custom objects) into one edge,
    merging their labels, so the diagram draws one arrow per connection
    instead of several stacked on top of each other."""
    merged: dict[tuple[str, str], DiagramEdge] = {}
    order: list[tuple[str, str]] = []
    for e in edges:
        key = (e.source, e.target)
        if key not in merged:
            merged[key] = DiagramEdge(source=e.source, target=e.target, label=e.label, cardinality=e.cardinality)
            order.append(key)
            continue
        existing = merged[key]
        labels = [part for part in existing.label.split("; ") if part]
        if e.label and e.label not in labels:
            labels.append(e.label)
        existing.label = "; ".join(labels)
        if existing.cardinality != e.cardinality:
            existing.cardinality = ""
    return [merged[key] for key in order]


def _condensed_label(label: str) -> str:
    """A dedupe-merged label like ``"a; b; c"`` becomes ``"a (+2)"`` on the
    diagram itself — full detail stays in the underlying table/export."""
    parts = [part for part in label.split("; ") if part]
    if len(parts) <= 1:
        return label
    return f"{parts[0]} (+{len(parts) - 1})"


# ---- builders ----------------------------------------------------------


def from_blueprint(blueprint: Blueprint) -> tuple[list[DiagramNode], list[DiagramEdge]]:
    nodes: dict[str, DiagramNode] = {}
    for obj_name, props in blueprint.standard_object_properties.items():
        nodes[obj_name] = DiagramNode(name=obj_name, kind="Standard", property_count=len(props))
    for obj_name in blueprint.inputs.standard_objects:
        nodes.setdefault(obj_name, DiagramNode(name=obj_name, kind="Standard"))
    for co in blueprint.custom_objects:
        nodes[co.name] = DiagramNode(name=co.name, kind="Custom", property_count=len(co.properties), notes=co.description)

    edges = [
        DiagramEdge(source=a.from_object, target=a.to_object, label=a.label, cardinality=a.cardinality)
        for a in blueprint.associations
    ]
    _ensure_endpoints(nodes, edges)
    return list(nodes.values()), dedupe_edges(edges)


def from_snapshot(
    snapshot: PortalSnapshot,
    findings: Optional[list[Finding]] = None,
    include_engagements: bool = False,
) -> tuple[list[DiagramNode], list[DiagramEdge]]:
    type_id_labels = dict(STANDARD_TYPE_ID_LABELS)
    type_id_labels.update(_ENGAGEMENT_TYPE_ID_LABELS)
    type_id_labels.update({s.object_type: s.label for s in snapshot.object_schemas})

    findings_by_object: dict[str, list[str]] = {}
    for f in findings or []:
        findings_by_object.setdefault(f.object_type, []).append(f.severity)

    nodes: dict[str, DiagramNode] = {}
    for schema in snapshot.object_schemas:
        severities = findings_by_object.get(schema.label, [])
        nodes[schema.label] = DiagramNode(
            name=schema.label,
            kind="Custom" if schema.is_custom else "Standard",
            property_count=len(schema.properties),
            risk=_worst_severity(severities),
            finding_count=len(severities),
        )

    edges: list[DiagramEdge] = []
    for schema in snapshot.object_schemas:
        for a in schema.associations:
            is_engagement = a.to_object in _ENGAGEMENT_TYPE_IDS
            if is_engagement and not include_engagements:
                continue
            target_label = type_id_labels.get(a.to_object, a.to_object)
            if is_engagement:
                nodes.setdefault(target_label, DiagramNode(name=target_label, kind="Activity"))
            edges.append(
                DiagramEdge(source=schema.label, target=target_label, label=a.label, cardinality=a.cardinality or "")
            )
    _ensure_endpoints(nodes, edges)
    return list(nodes.values()), dedupe_edges(edges)


# ---- audit chart helpers -------------------------------------------------


def findings_by_severity(findings: list[Finding]) -> dict[str, int]:
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def findings_by_area(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.area] = counts.get(f.area, 0) + 1
    return counts


# ---- rendering ------------------------------------------------------------


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _node_subtitle(n: DiagramNode) -> str:
    if n.kind == "Activity" and not n.property_count and not n.risk:
        return ""
    sub = f"{n.property_count} propert{'y' if n.property_count == 1 else 'ies'}"
    if n.risk:
        sub += f" · {n.finding_count} finding(s)"
    return sub


def _node_fill(n: DiagramNode) -> tuple[str, str]:
    """(fill color, font color) for a node's kind."""
    if n.kind == "Custom":
        return PURPLE, "white"
    if n.kind == "Activity":
        return BG_ALT, TEXT_BODY
    return "white", TEXT_DARK


def to_graphviz(nodes: list[DiagramNode], edges: list[DiagramEdge], show_labels: bool = True) -> str:
    known = {n.name for n in nodes}
    lines = [
        "digraph architecture {",
        "  rankdir=LR;",
        '  bgcolor="transparent";',
        "  concentrate=true;",  # merges shared edge paths into a hub node -- the single biggest declutter lever on a "hairball" graph
        "  nodesep=0.45;",
        "  ranksep=0.75;",
        '  node [fontname="Helvetica", fontsize=11, shape=box, style="rounded,filled"];',
        f'  edge [fontname="Helvetica", fontsize=9, color="{PURPLE_LIGHT}", fontcolor="{TEXT_DARK}"];',
    ]
    for n in nodes:
        fill, font_color = _node_fill(n)
        border = SEVERITY_COLORS.get(n.risk, BORDER)
        pen_width = 3 if n.risk else 1.5
        style = "rounded,filled,dashed" if n.kind == "Activity" else "rounded,filled"
        # Escape the name/subtitle independently, then join with a literal
        # "\n" (DOT's own newline escape) -- escaping the already-joined
        # string here would double the backslash and print a literal
        # "\n" in the rendered label instead of a line break.
        name_part = _dot_escape(n.name)
        sub_part = _dot_escape(_node_subtitle(n))
        label = f"{name_part}\\n{sub_part}" if sub_part else name_part
        lines.append(
            f'  "{name_part}" [label="{label}", fillcolor="{fill}", '
            f'fontcolor="{font_color}", color="{border}", penwidth={pen_width}, style="{style}"];'
        )
    for e in dedupe_edges(edges):
        if e.source not in known or e.target not in known:
            continue
        if show_labels:
            label = _dot_escape(_condensed_label(e.label or e.cardinality))
            lines.append(f'  "{_dot_escape(e.source)}" -> "{_dot_escape(e.target)}" [label="{label}"];')
        else:
            lines.append(f'  "{_dot_escape(e.source)}" -> "{_dot_escape(e.target)}";')
    lines.append("}")
    return "\n".join(lines)


def dangling_edges(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> list[DiagramEdge]:
    known = {n.name for n in nodes}
    return [e for e in edges if e.source not in known or e.target not in known]


# ---- exporters -------------------------------------------------------------


def diagram_to_json(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> str:
    payload = {
        "nodes": [dataclasses.asdict(n) for n in nodes],
        "edges": [dataclasses.asdict(e) for e in edges],
    }
    return json.dumps(payload, indent=2)


def nodes_edges_from_dicts(
    node_dicts: list[dict], edge_dicts: list[dict]
) -> tuple[list[DiagramNode], list[DiagramEdge]]:
    """Inverse of the ``{"nodes": [...], "edges": [...]}`` shape
    :func:`diagram_to_json` writes -- reconstructs typed nodes/edges from
    plain dicts (e.g. loaded back out of a saved Project Library snapshot)
    so callers can feed them straight into :func:`to_graphviz` again."""
    return [DiagramNode(**d) for d in node_dicts], [DiagramEdge(**d) for d in edge_dicts]


_KIND_ORDER = {"Standard": 0, "Custom": 1, "Activity": 2}


def _degree_map(edges: list[DiagramEdge]) -> dict[str, int]:
    degree: dict[str, int] = {}
    for e in edges:
        degree[e.source] = degree.get(e.source, 0) + 1
        degree[e.target] = degree.get(e.target, 0) + 1
    return degree


_MARGIN = 40.0
_COL_GAP = 70.0
_ROW_GAP = 170.0


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Greedy word-wrap ``text`` to at most ``max_chars`` per line -- used
    to size node boxes to their actual label instead of clipping/overflowing
    a fixed box (the previous 200x70 constant)."""
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    return lines


def _node_text_lines(n: DiagramNode) -> list[str]:
    lines = _wrap_text(n.name, 22)
    sub = _node_subtitle(n)
    if sub:
        lines.extend(_wrap_text(sub, 26))
    return lines


def _node_box_size(lines: list[str]) -> tuple[float, float]:
    max_len = max((len(line) for line in lines), default=4)
    width = min(260.0, max(170.0, 30.0 + max_len * 7.2))
    height = max(60.0, 28.0 + 20.0 * len(lines))
    return width, height


@dataclasses.dataclass
class _Box:
    x: float
    y: float
    w: float
    h: float
    lines: list[str]

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def bottom(self) -> float:
        return self.y + self.h


def _layout_boxes(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> dict[str, _Box]:
    """Position every node as a row-band-per-kind layered graph (Standard,
    then Custom, then Activity -- same top-to-bottom story as before), but
    order nodes *within* a band by the average x of their already-placed
    neighbors in earlier bands (a barycenter pass) instead of raw degree --
    this is what actually keeps edges from crossing all over the canvas,
    which is what made the old grid unreadable once a band had more than a
    handful of connections running through it."""
    degree = _degree_map(edges)
    neighbors: dict[str, list[str]] = {}
    for e in edges:
        neighbors.setdefault(e.source, []).append(e.target)
        neighbors.setdefault(e.target, []).append(e.source)

    bands: dict[int, list[DiagramNode]] = {}
    for n in nodes:
        bands.setdefault(_KIND_ORDER.get(n.kind, 1), []).append(n)

    boxes: dict[str, _Box] = {}
    y = _MARGIN
    for band_idx in sorted(bands):

        def sort_key(n: DiagramNode, _neighbors=neighbors, _boxes=boxes, _degree=degree) -> tuple:
            placed = [_boxes[nb].cx for nb in _neighbors.get(n.name, []) if nb in _boxes]
            if placed:
                return (0, sum(placed) / len(placed), n.name)
            return (1, float(-_degree.get(n.name, 0)), n.name)

        band_nodes = sorted(bands[band_idx], key=sort_key)

        x = _MARGIN
        row_h = 0.0
        for n in band_nodes:
            lines = _node_text_lines(n)
            w, h = _node_box_size(lines)
            boxes[n.name] = _Box(x=x, y=y, w=w, h=h, lines=lines)
            x += w + _COL_GAP
            row_h = max(row_h, h)
        y += row_h + _ROW_GAP

    return boxes


# (edge, waypoints, label position, exit anchor, entry anchor) -- an anchor
# is an (x-fraction, y-fraction) pair along the node's boundary, in the same
# 0..1 units draw.io's own exitX/exitY/entryX/entryY use.
_EdgeRoute = tuple[DiagramEdge, list[tuple[float, float]], tuple[float, float], tuple[float, float], tuple[float, float]]


def _label_half_width(e: DiagramEdge) -> float:
    """Rough rendered half-width (px) of an edge's label text, used so the
    collision check below compares actual label extents rather than just
    their center points -- two short labels can sit closer together than
    two long ones without touching."""
    text = _condensed_label(e.label or e.cardinality)
    return (7.0 * len(text) + 16.0) / 2 if text else 20.0


def _avoid_label_collisions(routes: list[_EdgeRoute], step: float = 18.0, max_shift: float = 180.0) -> list[_EdgeRoute]:
    """Nudge a label (and the waypoint segment it sits on) straight down in
    small steps until it clears every previously-placed label's estimated
    text width -- greedy, not globally optimal, but enough to stop labels
    overlapping each other or the node boxes below them."""
    placed: list[tuple[float, float, float]] = []
    result: list[_EdgeRoute] = []
    for e, points, (lx, ly), exit_anchor, entry_anchor in routes:
        half_w = _label_half_width(e)
        y = ly
        shift = 0.0
        while shift <= max_shift and any(
            abs(y - py) < step and abs(lx - px) < (half_w + pw + 10) for px, py, pw in placed
        ):
            shift += step
            y = ly + shift
        placed.append((lx, y, half_w))
        if len(points) == 4 and y != ly:
            (x0, y0), (x1, _y1), (x2, _y2), (x3, y3) = points
            points = [(x0, y0), (x1, y), (x2, y), (x3, y3)]
        result.append((e, points, (lx, y), exit_anchor, entry_anchor))
    return result


def _lane_is_clear(lane_y: float, x0: float, x1: float, boxes: dict[str, _Box], src_name: str, tgt_name: str) -> bool:
    """Whether a horizontal segment at ``lane_y`` spanning ``x0``..``x1``
    would cut through some *other* node's box -- true for any edge that
    skips over a row-band entirely (e.g. a Standard object associated
    directly to an Activity type, jumping clean over the Custom band)."""
    xlo, xhi = min(x0, x1), max(x0, x1)
    for name, b in boxes.items():
        if name in (src_name, tgt_name):
            continue
        if b.y - 1 <= lane_y <= b.bottom + 1 and b.x <= xhi and b.x + b.w >= xlo:
            return False
    return True


def _content_extent(boxes: dict[str, _Box], routes: list[_EdgeRoute]) -> tuple[float, float]:
    """Overall canvas size needed to fit every node box and every edge
    waypoint (a bypass rail can extend past the rightmost node)."""
    xs = [b.x + b.w for b in boxes.values()] + [px for _e, points, *_r in routes for px, _py in points]
    ys = [b.y + b.h for b in boxes.values()] + [py for _e, points, *_r in routes for _px, py in points]
    return max(xs, default=400.0) + _MARGIN, max(ys, default=300.0) + _MARGIN


def _edge_routes(edges: list[DiagramEdge], boxes: dict[str, _Box]) -> list[_EdgeRoute]:
    """Explicit waypoints per edge instead of leaving auto-routing to
    whatever opens the file: each node's outgoing edges fan out across its
    bottom (or top) edge instead of all leaving/entering dead-center, and
    each edge gets its own orthogonal lane between the two rows it
    connects. An edge that would have to cut through an unrelated row to
    get there is instead routed around it, on a dedicated side-rail --
    otherwise it draws a line (and a label) straight across whatever node
    happens to sit between its source and target rows."""
    valid = [e for e in dedupe_edges(edges) if e.source in boxes and e.target in boxes]

    out_order: dict[str, list[int]] = {}
    in_order: dict[str, list[int]] = {}
    for i, e in enumerate(valid):
        out_order.setdefault(e.source, []).append(i)
        in_order.setdefault(e.target, []).append(i)
    for idxs in out_order.values():
        idxs.sort(key=lambda i: boxes[valid[i].target].cx)
    for idxs in in_order.values():
        idxs.sort(key=lambda i: boxes[valid[i].source].cx)

    exit_frac: dict[int, float] = {}
    entry_frac: dict[int, float] = {}
    for idxs in out_order.values():
        n = len(idxs)
        for rank, i in enumerate(idxs):
            exit_frac[i] = (rank + 1) / (n + 1)
    for idxs in in_order.values():
        n = len(idxs)
        for rank, i in enumerate(idxs):
            entry_frac[i] = (rank + 1) / (n + 1)

    rail_base = max((b.x + b.w for b in boxes.values()), default=0.0) + 60.0
    bypass_rank = 0

    routes: list[_EdgeRoute] = []
    for i, e in enumerate(valid):
        src, tgt = boxes[e.source], boxes[e.target]
        ef, nf = exit_frac.get(i, 0.5), entry_frac.get(i, 0.5)
        ex, en = src.x + src.w * ef, tgt.x + tgt.w * nf

        if tgt.y > src.bottom - 1:
            sx, sy, tx, ty = ex, src.bottom, en, tgt.y
            lane_y = sy + (ty - sy) / 2
            exit_anchor, entry_anchor = (ef, 1.0), (nf, 0.0)
        elif tgt.bottom < src.y + 1:
            sx, sy, tx, ty = ex, src.y, en, tgt.bottom
            lane_y = ty + (sy - ty) / 2
            exit_anchor, entry_anchor = (ef, 0.0), (nf, 1.0)
        else:
            sx, sy, tx, ty = ex, src.bottom, en, tgt.bottom
            lane_y = max(sy, ty) + 46 + (i % 4) * 18
            exit_anchor, entry_anchor = (ef, 1.0), (nf, 1.0)

        points = [(sx, sy), (sx, lane_y), (tx, lane_y), (tx, ty)]

        if not _lane_is_clear(lane_y, sx, tx, boxes, e.source, e.target):
            rail_x = rail_base + bypass_rank * 26.0
            bypass_rank += 1
            fy, ty_f = min(0.85, max(0.15, ef)), min(0.85, max(0.15, nf))
            sy2, ty2 = src.y + src.h * fy, tgt.y + tgt.h * ty_f
            points = [(src.x + src.w, sy2), (rail_x, sy2), (rail_x, ty2), (tgt.x + tgt.w, ty2)]
            lane_y = (sy2 + ty2) / 2
            exit_anchor, entry_anchor = (1.0, fy), (1.0, ty_f)

        label_pos = ((points[1][0] + points[2][0]) / 2, lane_y)
        routes.append((e, points, label_pos, exit_anchor, entry_anchor))

    return _avoid_label_collisions(routes)


def to_drawio_xml(nodes: list[DiagramNode], edges: list[DiagramEdge], show_labels: bool = True) -> str:
    """Render as a diagrams.net (draw.io) ``.drawio`` file — plain XML, no
    external service or account involved. Open it at app.diagrams.net (or
    the desktop app) for full drag-and-drop editing: move objects, redraw
    connections, relabel anything the generator or audit got wrong.

    Nodes are grouped into row-bands by kind (Standard, then Custom, then
    Activity) and positioned with :func:`_layout_boxes`; edges are drawn
    along explicit waypoints from :func:`_edge_routes` rather than left to
    draw.io's own auto-router, so the file looks the same the moment it's
    opened as it does in :func:`to_png_bytes`."""
    deduped = dedupe_edges(edges)
    degree = _degree_map(deduped)
    ordered_nodes = sorted(nodes, key=lambda n: (_KIND_ORDER.get(n.kind, 1), -degree.get(n.name, 0), n.name))
    boxes = _layout_boxes(ordered_nodes, deduped)
    routes = _edge_routes(deduped, boxes)

    id_of: dict[str, str] = {}
    cells: list[str] = ['<mxCell id="0" />', '<mxCell id="1" parent="0" />']

    for i, n in enumerate(ordered_nodes):
        box = boxes[n.name]
        fill, font_color = _node_fill(n)
        fill = "#FFFFFF" if fill == "white" else fill
        stroke = SEVERITY_COLORS.get(n.risk, BORDER)
        stroke_width = 3 if n.risk else 1
        dashed = "dashed=1;" if n.kind == "Activity" else ""
        # value is an XML attribute, so literal "<br>" must be entity-escaped
        # here; draw.io un-escapes it and interprets the result as HTML
        # because the style below sets html=1.
        value = "&lt;br&gt;".join(escape(line) for line in box.lines)
        style = escape(
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};fontColor={font_color};"
            f"strokeColor={stroke};strokeWidth={stroke_width};arcSize=12;fontSize=11;{dashed}"
        )
        node_id = f"node_{i}"
        id_of[n.name] = node_id
        cells.append(
            f'<mxCell id="{node_id}" value="{value}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{box.x:.0f}" y="{box.y:.0f}" width="{box.w:.0f}" height="{box.h:.0f}" as="geometry" /></mxCell>'
        )

    for i, (e, points, _label_pos, (exit_x, exit_y), (entry_x, entry_y)) in enumerate(routes):
        src, tgt = id_of.get(e.source), id_of.get(e.target)
        if not src or not tgt:
            continue
        label = escape(_condensed_label(e.label or e.cardinality)) if show_labels else ""
        style = escape(
            "edgeStyle=none;rounded=1;html=1;fontSize=10;labelBackgroundColor=#FFFFFF;"
            f"strokeColor={PURPLE_LIGHT};exitX={exit_x:.3f};exitY={exit_y:.3f};exitDx=0;exitDy=0;"
            f"entryX={entry_x:.3f};entryY={entry_y:.3f};entryDx=0;entryDy=0;"
        )
        waypoints = "".join(f'<mxPoint x="{px:.0f}" y="{py:.0f}" />' for px, py in points[1:-1])
        cells.append(
            f'<mxCell id="edge_{i}" value="{label}" style="{style}" edge="1" parent="1" '
            f'source="{src}" target="{tgt}">'
            f'<mxGeometry relative="1" as="geometry"><Array as="points">{waypoints}</Array></mxGeometry></mxCell>'
        )

    total_w, total_h = _content_extent(boxes, routes)

    body = "".join(cells)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<mxfile host="architecturescope">'
        '<diagram name="Architecture">'
        f'<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
        f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{total_w:.0f}" pageHeight="{total_h:.0f}" math="0" shadow="0">'
        f"<root>{body}</root>"
        "</mxGraphModel></diagram></mxfile>"
    )


def to_png_bytes(nodes: list[DiagramNode], edges: list[DiagramEdge], show_labels: bool = True) -> bytes:
    """Render the same layout used by :func:`to_drawio_xml` (same node
    boxes, same edge waypoints) as a flat PNG — a one-click, no-editor way
    to preview or drop the diagram straight into a slide/doc."""
    import io as _io

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    deduped = dedupe_edges(edges)
    degree = _degree_map(deduped)
    ordered_nodes = sorted(nodes, key=lambda n: (_KIND_ORDER.get(n.kind, 1), -degree.get(n.name, 0), n.name))
    boxes = _layout_boxes(ordered_nodes, deduped)
    routes = _edge_routes(deduped, boxes)

    width, height = _content_extent(boxes, routes)

    dpi = 130
    fig, ax = plt.subplots(figsize=(max(width, 1.0) / 100, max(height, 1.0) / 100), dpi=dpi)
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.invert_yaxis()
    ax.axis("off")
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)

    if ordered_nodes:
        ax.text(
            _MARGIN, 16,
            "Purple = custom object · White = standard object · Dashed = HubSpot activity · "
            "Border color = worst finding severity",
            fontsize=7, color=TEXT_BODY, ha="left", va="center",
        )

    for e, points, (lx, ly), *_sides in routes:
        xs = [p[0] for p in points[:-1]]
        ys = [p[1] for p in points[:-1]]
        if len(xs) > 1:
            ax.plot(xs, ys, color=PURPLE_LIGHT, linewidth=1.1, zorder=1, solid_capstyle="round")
        ax.annotate(
            "", xy=points[-1], xytext=points[-2],
            arrowprops=dict(arrowstyle="-|>", color=PURPLE_LIGHT, lw=1.1, shrinkA=0, shrinkB=2),
            zorder=1,
        )
        if show_labels:
            text = _condensed_label(e.label or e.cardinality)
            if text:
                ax.text(
                    lx, ly, text, fontsize=7, ha="center", va="center", color=TEXT_DARK, zorder=3,
                    bbox=dict(facecolor="white", edgecolor="none", pad=1.5, alpha=0.92),
                )

    for n in ordered_nodes:
        box = boxes[n.name]
        fill, font_color = _node_fill(n)
        fill = "#FFFFFF" if fill == "white" else fill
        stroke = SEVERITY_COLORS.get(n.risk, BORDER)
        patch = FancyBboxPatch(
            (box.x, box.y), box.w, box.h,
            boxstyle="round,pad=0,rounding_size=8",
            linewidth=2.2 if n.risk else 1.1,
            edgecolor=stroke, facecolor=fill,
            linestyle="dashed" if n.kind == "Activity" else "solid",
            zorder=2,
        )
        ax.add_patch(patch)
        ax.text(
            box.cx, box.y + box.h / 2, "\n".join(box.lines),
            fontsize=8.5, ha="center", va="center", color=font_color, zorder=3, linespacing=1.4,
        )

    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    return buf.getvalue()
