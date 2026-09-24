"""Shared dataclasses for the Architecture Generator (Module 1), the
Documentation Generator (Module 3), and the Portal Auditor (Module 2).

Plain dataclasses only — no extra serialization dependency. JSON export is
``json.dumps(dataclasses.asdict(blueprint), ...)`` (see core/blueprint.py).

Severity is a plain string ("High"/"Medium"/"Low") rather than an Enum:
mixing str+Enum has a well-known str()/format() inconsistency across Python
versions, and a plain string keeps CSV/Markdown export and comparisons
trivial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BlueprintInput:
    project_name: str = "Untitled Project"
    standard_objects: list[str] = field(default_factory=list)
    custom_object_keywords: list[str] = field(default_factory=list)
    custom_object_notes: str = ""
    pipelines_required: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    other_integration_notes: str = ""
    record_volumes: dict[str, int] = field(default_factory=dict)
    hubs_in_scope: list[str] = field(default_factory=list)


@dataclass
class PropertyDef:
    name: str
    label: str
    type: str
    field_type: str = "text"
    group: str = "custom_properties"
    description: str = ""
    options: Optional[list[str]] = None
    required: bool = False


@dataclass
class CustomObjectDef:
    name: str
    plural_label: str
    description: str = ""
    properties: list[PropertyDef] = field(default_factory=list)


@dataclass
class AssociationDef:
    from_object: str
    to_object: str
    label: str
    cardinality: str = "many-to-many"


@dataclass
class StageDef:
    name: str
    order: int
    is_closed: bool = False
    is_won: bool = False


@dataclass
class PipelineDef:
    object_type: str
    name: str
    stages: list[StageDef] = field(default_factory=list)


@dataclass
class WorkflowSuggestion:
    name: str
    object_type: str
    trigger: str
    action_summary: str
    overwrite_risk: bool = False
    risk_reason: str = ""


@dataclass
class Blueprint:
    project_name: str
    generated_at: str
    inputs: BlueprintInput
    custom_objects: list[CustomObjectDef] = field(default_factory=list)
    standard_object_properties: dict[str, list[PropertyDef]] = field(default_factory=dict)
    associations: list[AssociationDef] = field(default_factory=list)
    pipelines: list[PipelineDef] = field(default_factory=list)
    naming_conventions: dict[str, str] = field(default_factory=dict)
    base_currency_note: str = ""
    workflows: list[WorkflowSuggestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---- Module 3 (Documentation Generator) / shared with Module 2 -----------


@dataclass
class PortalPropertyDef:
    name: str
    label: str
    type: str
    field_type: str = ""
    group_name: str = ""
    options: list[str] = field(default_factory=list)
    description: str = ""
    hubspot_defined: bool = False


@dataclass
class ObjectSchema:
    object_type: str
    label: str
    is_custom: bool
    singular_label: str = ""
    properties: list[PortalPropertyDef] = field(default_factory=list)
    associations: list[AssociationDef] = field(default_factory=list)


@dataclass
class PortalPipelineStage:
    stage_id: str
    label: str
    display_order: int = 0


@dataclass
class PortalPipeline:
    object_type: str
    pipeline_id: str
    label: str
    stages: list[PortalPipelineStage] = field(default_factory=list)


@dataclass
class PortalWorkflow:
    workflow_id: str
    name: str
    enabled: bool
    object_type: str
    re_enrollment_enabled: bool = False
    actions: list[dict] = field(default_factory=list)


@dataclass
class Owner:
    owner_id: str
    email: str
    first_name: str
    last_name: str
    teams: list[str] = field(default_factory=list)
    archived: bool = False


@dataclass
class Team:
    team_id: str
    name: str
    member_count: int = 0


@dataclass
class PortalSnapshot:
    pulled_at: str
    object_schemas: list[ObjectSchema] = field(default_factory=list)
    pipelines: list[PortalPipeline] = field(default_factory=list)
    workflows: list[PortalWorkflow] = field(default_factory=list)
    owners: list[Owner] = field(default_factory=list)
    teams: list[Team] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---- Module 2 (Portal Auditor) --------------------------------------------

SEVERITIES = ["High", "Medium", "Low"]


@dataclass
class Finding:
    area: str
    description: str
    severity: str
    recommended_fix: str
    object_type: str = ""
