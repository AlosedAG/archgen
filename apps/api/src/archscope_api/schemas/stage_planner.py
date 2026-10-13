"""Deal Stage Planner (pre-call template) contract."""

from __future__ import annotations

from pydantic import Field

from .base import ApiModel
from .blueprint import PipelineDef, PropertyDef, WorkflowSuggestion


class PlannedStage(ApiModel):
    name: str
    forecast: float | None = Field(None, description="Win probability as a percentage, 0–100.")
    entry_criteria: str = ""
    exit_criteria: str = ""
    actions: str = ""
    automations: str = ""
    fields: list[str] = Field(default_factory=list, description="Deal properties required at this stage.")


class PlannedProperty(ApiModel):
    label: str
    stages: list[str] = Field(description="Stages that require it.")
    existing: str = Field("", description="HubSpot's own property it maps to (not created), if any.")
    definition: PropertyDef | None = None


class PlannerBuildItem(ApiModel):
    key: str
    section: str
    name: str
    source: str


class StagePlannerImport(ApiModel):
    """A parsed planner plus what it would populate — for review before
    anything is applied."""

    stages: list[PlannedStage]
    warnings: list[str] = Field(description="Columns / rows skipped or guessed at while parsing.")
    source: str = Field(description="The sheet that was read.")
    discovery_answer: str = Field(description="The Discovery Processes 'Sales pipeline stages' answer.")
    discovery_notes: str = Field(description="Block for the Processes notes, between [Deal Stage Planner] markers.")
    pipeline: PipelineDef
    properties: list[PlannedProperty]
    workflows: list[WorkflowSuggestion]
    build_items: list[PlannerBuildItem]


class StagePlannerPreviewRequest(ApiModel):
    """Reviewed (possibly edited) stages to map again."""

    stages: list[PlannedStage] = Field(max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=200)
    source: str = Field("", max_length=300)
