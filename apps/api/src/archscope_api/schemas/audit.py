"""Portal Auditor (Module 2) and Property Audit (Module 2B) contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archscope_domain.property_audit import PropertyAuditResult as DomainPropertyAuditResult

from .base import ApiModel, to_domain
from .portal import Finding, PortalSnapshot

PropertyRating = Literal["Keep", "Review", "Remove candidate"]


class AuditRequest(ApiModel):
    snapshot: PortalSnapshot


class AuditResult(ApiModel):
    """Best-practice findings for one snapshot, highest severity first,
    plus the counts dashboards chart."""

    findings: list[Finding]
    by_severity: dict[str, int] = Field(description="Finding count per severity, every severity present.")
    by_area: dict[str, int] = Field(description="Finding count per audit area.")


class PropertyAuditRequest(ApiModel):
    snapshot: PortalSnapshot


class PropertyAuditRow(ApiModel):
    object_label: str
    object_type: str
    property_label: str
    internal_name: str
    field_type: str
    is_custom: bool
    fill_pct: float = Field(ge=0, le=100, description="Percent of sampled records with a value (0–100).")
    uses: int = Field(ge=0, description="Workflows that reference the property.")
    rating: PropertyRating
    assessment: str = ""


class ObjectAuditSummary(ApiModel):
    object_label: str
    object_type: str
    properties_count: int
    custom_count: int
    remove_count: int
    review_count: int
    keep_count: int
    cleanup_score: float = Field(ge=0, le=100)


class PropertyAuditResult(ApiModel):
    generated_at: str
    sample_size: int
    rows: list[PropertyAuditRow] = Field(default_factory=list)
    object_summaries: list[ObjectAuditSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, result: DomainPropertyAuditResult) -> PropertyAuditResult:
        return cls.model_validate(result)

    def to_domain(self) -> DomainPropertyAuditResult:
        return to_domain(self, DomainPropertyAuditResult)


class PropertyAuditExportRequest(ApiModel):
    result: PropertyAuditResult
    project_name: str = Field("", max_length=200)
