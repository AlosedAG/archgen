"""Executive Report (Module 4) contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from archscope_domain.report import ReportContext as DomainReportContext

from .base import ApiModel
from .portal import Finding, PortalSnapshot

HealthRating = Literal["Excellent", "Good", "Fair", "Needs Attention", "Not Yet Audited"]


class ReportRequest(ApiModel):
    snapshot: PortalSnapshot
    findings: list[Finding] | None = Field(
        None, description="Audit findings for this snapshot; omit (null) when no audit was run — the report then says so."
    )
    project_name: str = Field("", max_length=200)


class NameCount(ApiModel):
    name: str
    count: int


def _pairs_to_name_counts(value: Any) -> Any:
    """The domain keeps (name, count) tuples; the API exposes objects,
    which are self-describing in JSON and in the generated TS types."""
    if isinstance(value, list):
        return [{"name": v[0], "count": v[1]} if isinstance(v, (tuple, list)) else v for v in value]
    return value


class ObjectSummary(ApiModel):
    label: str
    object_type: str
    is_custom: bool
    property_count: int
    top_groups: list[NameCount] = Field(default_factory=list)
    association_count: int = 0
    association_targets: list[str] = Field(default_factory=list)

    _top_groups = field_validator("top_groups", mode="before")(_pairs_to_name_counts)


class PipelineSummary(ApiModel):
    object_type: str
    pipeline_count: int
    total_stage_count: int
    pipelines: list[NameCount] = Field(default_factory=list, description="Pipeline label and its stage count.")

    _pipelines = field_validator("pipelines", mode="before")(_pairs_to_name_counts)


class FindingGroup(ApiModel):
    area: str
    severity: str
    count: int
    object_types: list[str] = Field(default_factory=list)
    items: list[Finding] = Field(default_factory=list)


class ReportContext(ApiModel):
    """Every number and grouping the executive report shows — computed
    once, so the client and internal documents never disagree."""

    generated_at: str
    project_name: str
    snapshot: PortalSnapshot
    audited: bool
    standard_object_count: int
    custom_object_count: int
    total_properties: int
    object_summaries: list[ObjectSummary]
    pipeline_summaries: list[PipelineSummary]
    total_pipelines: int
    total_stages: int
    workflow_total: int
    workflow_enabled: int
    workflow_disabled: int
    workflow_unnamed: int
    team_total: int
    team_empty: int
    owner_total: int
    owner_unassigned: int
    owner_archived: int
    association_total: int
    finding_total: int
    severity_counts: dict[str, int]
    finding_groups: list[FindingGroup]
    rating: HealthRating
    rating_reason: str

    @classmethod
    def from_domain(cls, ctx: DomainReportContext) -> ReportContext:
        return cls.model_validate(ctx)
