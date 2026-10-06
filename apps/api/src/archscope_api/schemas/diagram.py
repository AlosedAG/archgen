"""Architecture Diagram (Module 5) contract: a node/edge graph the web app
renders interactively, plus server-side renders (DOT, draw.io, PNG)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archscope_domain import diagram as dd

from .base import ApiModel, to_domain
from .blueprint import Blueprint
from .portal import Finding, PortalSnapshot

NodeKind = Literal["Standard", "Custom", "Activity"]
Risk = Literal["", "Low", "Medium", "High"]


class DiagramNode(ApiModel):
    name: str
    kind: NodeKind = "Standard"
    property_count: int = 0
    risk: Risk = Field("", description="Worst finding severity for this object; empty when none.")
    finding_count: int = 0
    notes: str = ""


class DiagramEdge(ApiModel):
    source: str
    target: str
    label: str = ""
    cardinality: str = "many-to-many"


class Diagram(ApiModel):
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    dangling_edges: list[DiagramEdge] = Field(
        default_factory=list, description="Edges whose source or target isn't a node; renderers skip them."
    )

    @classmethod
    def from_domain(cls, nodes: list[dd.DiagramNode], edges: list[dd.DiagramEdge]) -> Diagram:
        return cls.model_validate({"nodes": nodes, "edges": edges, "dangling_edges": dd.dangling_edges(nodes, edges)})

    def to_domain(self) -> tuple[list[dd.DiagramNode], list[dd.DiagramEdge]]:
        return [to_domain(n, dd.DiagramNode) for n in self.nodes], [to_domain(e, dd.DiagramEdge) for e in self.edges]


class DiagramFromBlueprintRequest(ApiModel):
    blueprint: Blueprint


class DiagramFromSnapshotRequest(ApiModel):
    snapshot: PortalSnapshot
    findings: list[Finding] | None = None
    include_engagements: bool = Field(False, description="Include calls/emails/meetings/notes/tasks associations.")


class DiagramRenderRequest(ApiModel):
    diagram: Diagram
    show_labels: bool = True
