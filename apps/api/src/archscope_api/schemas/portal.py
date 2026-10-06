"""Portal snapshot + audit findings: the read-only picture of a live
HubSpot portal that the audit, report, and diagram modules all consume.
Snapshots flow both ways (pulled, returned, then posted back to the
audit/report/diagram endpoints), so the same models serve requests and
responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from archscope_domain import models as dm

from .base import ApiModel, to_domain
from .blueprint import AssociationDef

Severity = Literal["High", "Medium", "Low"]


class PortalPropertyDef(ApiModel):
    name: str
    label: str
    type: str
    field_type: str = ""
    group_name: str = ""
    options: list[str] = Field(default_factory=list)
    description: str = ""
    hubspot_defined: bool = False


class ObjectSchema(ApiModel):
    object_type: str
    label: str
    is_custom: bool
    singular_label: str = ""
    properties: list[PortalPropertyDef] = Field(default_factory=list)
    associations: list[AssociationDef] = Field(default_factory=list)


class PortalPipelineStage(ApiModel):
    stage_id: str
    label: str
    display_order: int = 0


class PortalPipeline(ApiModel):
    object_type: str
    pipeline_id: str
    label: str
    stages: list[PortalPipelineStage] = Field(default_factory=list)


class PortalWorkflow(ApiModel):
    workflow_id: str
    name: str
    enabled: bool
    object_type: str
    re_enrollment_enabled: bool = False
    actions: list[dict[str, Any]] = Field(default_factory=list)


class Owner(ApiModel):
    owner_id: str
    email: str
    first_name: str
    last_name: str
    teams: list[str] = Field(default_factory=list)
    archived: bool = False


class Team(ApiModel):
    team_id: str
    name: str
    member_count: int = 0


class PortalSnapshot(ApiModel):
    """Everything pulled from one portal at ``pulled_at``. Partial pulls are
    normal: a missing scope becomes a ``warnings`` entry, not an error."""

    pulled_at: str
    object_schemas: list[ObjectSchema] = Field(default_factory=list)
    pipelines: list[PortalPipeline] = Field(default_factory=list)
    workflows: list[PortalWorkflow] = Field(default_factory=list)
    owners: list[Owner] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, snapshot: dm.PortalSnapshot) -> PortalSnapshot:
        return cls.model_validate(snapshot)

    def to_domain(self) -> dm.PortalSnapshot:
        return to_domain(self, dm.PortalSnapshot)


class Finding(ApiModel):
    area: str
    description: str
    severity: Severity
    recommended_fix: str
    object_type: str = ""

    def to_domain(self) -> dm.Finding:
        return to_domain(self, dm.Finding)


def findings_from_domain(findings: list[dm.Finding]) -> list[Finding]:
    return [Finding.model_validate(f) for f in findings]


def findings_to_domain(findings: list[Finding] | None) -> list[dm.Finding] | None:
    return None if findings is None else [f.to_domain() for f in findings]
