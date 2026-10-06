"""Architecture Generator (Module 1) and Architecture Diagram (Module 5)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response
from fastapi.responses import PlainTextResponse

from ...schemas.blueprint import Blueprint, BlueprintInput
from ...schemas.diagram import Diagram, DiagramFromBlueprintRequest, DiagramFromSnapshotRequest, DiagramRenderRequest
from ...schemas.portal import findings_to_domain
from ...services import architecture
from ..deps import binary_responses, file_response, offload

router = APIRouter(tags=["architecture"])


@router.post("/blueprints", response_model=Blueprint, summary="Generate an architecture blueprint")
async def generate_blueprint(body: BlueprintInput) -> Blueprint:
    """Objects, properties, associations, pipelines, naming conventions and
    workflow suggestions for the engagement, following the rules in
    ``config/rules.yaml``. Deterministic apart from ``generated_at``."""
    blueprint = await offload(architecture.generate_blueprint, body.to_domain())
    return Blueprint.from_domain(blueprint)


@router.post(
    "/blueprints/markdown",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/markdown": {}}}},
    summary="Render a blueprint as Markdown",
)
async def blueprint_markdown(body: Blueprint) -> PlainTextResponse:
    text = await offload(architecture.blueprint_markdown, body.to_domain())
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


@router.post("/diagrams/from-blueprint", response_model=Diagram, summary="Diagram a proposed architecture")
async def diagram_from_blueprint(body: DiagramFromBlueprintRequest) -> Diagram:
    nodes, edges = await offload(architecture.diagram_from_blueprint, body.blueprint.to_domain())
    return Diagram.from_domain(nodes, edges)


@router.post("/diagrams/from-snapshot", response_model=Diagram, summary="Diagram a live portal, with audit risk")
async def diagram_from_snapshot(body: DiagramFromSnapshotRequest) -> Diagram:
    nodes, edges = await offload(
        architecture.diagram_from_snapshot,
        body.snapshot.to_domain(),
        findings_to_domain(body.findings),
        body.include_engagements,
    )
    return Diagram.from_domain(nodes, edges)


@router.post(
    "/diagrams/render",
    response_class=Response,
    responses=binary_responses("png", "dot", "drawio"),
    summary="Render a diagram (PNG, Graphviz DOT, or draw.io)",
)
async def render_diagram(body: DiagramRenderRequest, format: Literal["png", "dot", "drawio"] = Query("png")) -> Response:
    content = await offload(architecture.render_diagram, body.diagram.to_domain(), format, show_labels=body.show_labels)
    return file_response(content, stem="architecture_diagram", ext=format)
