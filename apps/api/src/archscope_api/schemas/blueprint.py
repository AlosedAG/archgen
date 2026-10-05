"""Architecture Generator (Module 1) contract."""

from __future__ import annotations

from pydantic import Field

from archscope_domain import models as dm

from .base import ApiModel, to_domain


class BlueprintInput(ApiModel):
    """What the architect knows about the engagement."""

    project_name: str = Field("Untitled Project", min_length=1, max_length=200)
    standard_objects: list[str] = Field(default_factory=list, max_length=50, examples=[["Contact", "Company", "Deal"]])
    custom_object_keywords: list[str] = Field(default_factory=list, max_length=100)
    custom_object_notes: str = Field("", max_length=10_000)
    pipelines_required: list[str] = Field(default_factory=list, max_length=50)
    regions: list[str] = Field(default_factory=list, max_length=50)
    currencies: list[str] = Field(default_factory=list, max_length=50)
    integrations: list[str] = Field(default_factory=list, max_length=100)
    other_integration_notes: str = Field("", max_length=10_000)
    record_volumes: dict[str, int] = Field(default_factory=dict)
    hubs_in_scope: list[str] = Field(default_factory=list, max_length=20)

    def to_domain(self) -> dm.BlueprintInput:
        return to_domain(self, dm.BlueprintInput)


class PropertyDef(ApiModel):
    name: str
    label: str
    type: str
    field_type: str = "text"
    group: str = "custom_properties"
    description: str = ""
    options: list[str] | None = None
    required: bool = False


class CustomObjectDef(ApiModel):
    name: str
    plural_label: str
    description: str = ""
    properties: list[PropertyDef] = Field(default_factory=list)


class AssociationDef(ApiModel):
    from_object: str
    to_object: str
    label: str
    cardinality: str = "many-to-many"


class StageDef(ApiModel):
    name: str
    order: int
    is_closed: bool = False
    is_won: bool = False


class PipelineDef(ApiModel):
    object_type: str
    name: str
    stages: list[StageDef] = Field(default_factory=list)


class WorkflowSuggestion(ApiModel):
    name: str
    object_type: str
    trigger: str
    action_summary: str
    overwrite_risk: bool = False
    risk_reason: str = ""


class Blueprint(ApiModel):
    """A generated HubSpot architecture: objects, properties, associations,
    pipelines, naming conventions, and workflow suggestions (each flagged
    for overwrite risk)."""

    project_name: str
    generated_at: str
    inputs: BlueprintInput
    custom_objects: list[CustomObjectDef] = Field(default_factory=list)
    standard_object_properties: dict[str, list[PropertyDef]] = Field(default_factory=dict)
    associations: list[AssociationDef] = Field(default_factory=list)
    pipelines: list[PipelineDef] = Field(default_factory=list)
    naming_conventions: dict[str, str] = Field(default_factory=dict)
    base_currency_note: str = ""
    workflows: list[WorkflowSuggestion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, blueprint: dm.Blueprint) -> Blueprint:
        return cls.model_validate(blueprint)

    def to_domain(self) -> dm.Blueprint:
        return to_domain(self, dm.Blueprint)
