"""Deal Stage Planner use cases: the pre-call template and importing a filled-out copy."""

from __future__ import annotations

from dataclasses import dataclass

from archscope_domain import discovery as dd
from archscope_domain import stage_planner as sp
from archscope_domain.discovery_build_order import ExtraItem
from archscope_domain.models import PipelineDef, WorkflowSuggestion


def _config() -> sp.StagePlannerConfig:
    return sp.load_stage_planner_config(dd.discovery_build_order())


def template() -> bytes:
    return sp.build_template(_config())


@dataclass(frozen=True)
class PlannerImport:
    planner: sp.StagePlanner
    discovery_answer: str
    discovery_notes: str
    pipeline: PipelineDef
    properties: list[sp.PlannedProperty]
    workflows: list[WorkflowSuggestion]
    build_items: list[ExtraItem]


def parse(content: bytes, *, source: str = "") -> PlannerImport:
    """Parse a filled-out planner and preview what it maps to. Raises
    :class:`archscope_domain.stage_planner.StagePlannerParseError` if it
    isn't a readable planner."""
    config = _config()
    return preview(sp.parse_stage_planner(content, config, source=source))


def preview(planner: sp.StagePlanner) -> PlannerImport:
    """What a (reviewed) planner maps to: the Discovery answer and notes,
    the pipeline, deal properties, workflows and build-order items."""
    config = _config()
    return PlannerImport(
        planner=planner,
        discovery_answer=sp.to_discovery_answer(planner),
        discovery_notes=sp.to_discovery_notes(planner, config),
        pipeline=sp.to_pipeline(planner, config),
        properties=sp.to_deal_properties(planner, config),
        workflows=sp.to_workflows(planner, config),
        build_items=sp.to_build_items(planner, config),
    )


def build_items(planner: sp.StagePlanner) -> list[ExtraItem]:
    return sp.to_build_items(planner, _config())
