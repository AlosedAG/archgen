"""Context-aware suggestions ("Fill from earlier steps" / "Suggest") contract.

The page sends what the project already holds (it has it loaded) plus its
own current values; the API asks the model and returns those values with
blanks filled — never anything the user typed overwritten."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import ApiModel
from .discovery import DiscoveryNotes
from .proposal import ProposalDocument
from .stage_planner import PlannedStage


class AssistContext(ApiModel):
    discovery: DiscoveryNotes | None = Field(None, description="The discovery call notes, if any.")
    business_analysis: str = Field("", max_length=60_000, description="The drafted business analysis (Markdown).")
    documents: dict[str, dict[str, list[dict[str, Any]]]] = Field(
        default_factory=dict,
        description='Earlier documents as {title: {section: rows}}, e.g. {"Requirements Document": {...}}.',
    )
    stage_planner: list[PlannedStage] = Field(default_factory=list, description="An applied Deal Stage Planner's stages.")


class StagePlannerAssistRequest(ApiModel):
    context: AssistContext
    stages: list[PlannedStage] = Field(default_factory=list, description="The planner's current stages (may be empty).")


class StagePlannerAssistResponse(ApiModel):
    stages: list[PlannedStage]
    filled: int = Field(description="How many cells were filled.")
    model: str


class ArchitectureInputs(ApiModel):
    standard_objects: list[str] = Field(default_factory=list)
    custom_object_keywords: list[str] = Field(default_factory=list)
    custom_object_notes: str = ""
    pipelines_required: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    currencies: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    other_integration_notes: str = ""
    record_volumes: dict[str, int] = Field(default_factory=dict)
    hubs_in_scope: list[str] = Field(default_factory=list)


class ArchitectureAssistRequest(ApiModel):
    context: AssistContext
    inputs: ArchitectureInputs


class ArchitectureAssistResponse(ApiModel):
    inputs: ArchitectureInputs
    added: int = Field(description="How many values were added.")
    model: str


class ProposalAssistRequest(ApiModel):
    context: AssistContext
    proposal: ProposalDocument


class ProposalAssistResponse(ApiModel):
    proposal: ProposalDocument
    changed: list[str] = Field(description="Proposal fields that received suggestions, e.g. executive_summary, scope.")
    model: str


# ---- Industry templates --------------------------------------------------------


class TemplateChoice(ApiModel):
    id: str
    label: str
    description: str = ""


class IndustryTemplates(ApiModel):
    industries: list[TemplateChoice]
    sizes: list[TemplateChoice]


class IndustryDiscoveryRequest(ApiModel):
    industry: str
    size: str | None = None
    notes: DiscoveryNotes


class IndustryDiscoveryResponse(ApiModel):
    notes: DiscoveryNotes
    filled: int = Field(description="How many unanswered questions received the template's answer.")


class IndustryProposalRequest(ApiModel):
    industry: str
    size: str | None = None
    proposal: ProposalDocument


class IndustryProposalResponse(ApiModel):
    proposal: ProposalDocument
    changed: list[str]
