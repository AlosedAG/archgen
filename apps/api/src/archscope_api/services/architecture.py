"""Blueprint generation and architecture diagrams (Modules 1 and 5)."""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Literal

from archscope_domain import diagram as dd
from archscope_domain.blueprint import BlueprintGenerator, blueprint_to_markdown
from archscope_domain.models import Blueprint, BlueprintInput, Finding, PortalSnapshot
from archscope_domain.rules import RulesEngine

Graph = tuple[list[dd.DiagramNode], list[dd.DiagramEdge]]
DiagramFormat = Literal["dot", "drawio", "png"]

# matplotlib.pyplot keeps global figure state; renders must not interleave
# across threadpool workers.
_png_lock = threading.Lock()


@lru_cache
def rules_engine() -> RulesEngine:
    """The best-practice rules, parsed once per process."""
    return RulesEngine()


def generate_blueprint(bp_input: BlueprintInput) -> Blueprint:
    return BlueprintGenerator(rules_engine()).generate(bp_input)


def blueprint_markdown(blueprint: Blueprint) -> str:
    return blueprint_to_markdown(blueprint)


def diagram_from_blueprint(blueprint: Blueprint) -> Graph:
    return dd.from_blueprint(blueprint)


def diagram_from_snapshot(snapshot: PortalSnapshot, findings: list[Finding] | None, include_engagements: bool) -> Graph:
    return dd.from_snapshot(snapshot, findings, include_engagements=include_engagements)


def render_diagram(graph: Graph, fmt: DiagramFormat, *, show_labels: bool) -> bytes:
    nodes, edges = graph
    if fmt == "dot":
        return dd.to_graphviz(nodes, edges, show_labels=show_labels).encode("utf-8")
    if fmt == "drawio":
        return dd.to_drawio_xml(nodes, edges, show_labels=show_labels).encode("utf-8")
    with _png_lock:
        return dd.to_png_bytes(nodes, edges, show_labels=show_labels)
