"""Proposal & SOW Builder (Module 10) contract.

The domain stores a proposal as a versioned JSON document whose tables are
lists of rows keyed by their human column labels ("Acceptance Criteria",
"Add to Total", ...), exactly as the PDF prints them. The API exposes the
same document with typed, snake_case row models instead. Each row field's
``title`` *is* its column label, which is what makes the mapping in both
directions generic and lossless (:meth:`TableRow.to_row` /
:meth:`TableRow.from_row`).
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, Self

from pydantic import Field, model_validator

from archscope_domain import proposal as dp

from .base import ApiModel

ScopeStatus = Literal["In Scope", "Out of Scope", "Optional Add-on", "Client Responsibility"]
Billing = Literal["One Time", "Monthly", "Per Unit", "Per Year", "Hourly"]
KpiType = Literal["Primary", "Secondary"]
DocumentType = Literal["Proposal + Statement of Work", "Proposal", "Statement of Work"]
Coverage = Literal["Covered", "Not covered", "Available as add-on", "Client responsibility", "Excluded"]


class TableRow(ApiModel):
    """One table row. Field titles are the domain's column labels."""

    def to_row(self) -> dict[str, Any]:
        return {field.title or name: getattr(self, name) for name, field in type(self).model_fields.items()}

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Self:
        values = {name: row[field.title] for name, field in cls.model_fields.items() if field.title in row}
        return cls.model_validate(values)


class ObjectiveRow(TableRow):
    objective: str = Field("", title="Objective")
    success_measure: str = Field("", title="Success Measure")


class RequirementRow(TableRow):
    id: str = Field("", title="ID", description="Assigned (R-01, R-02, ...) when blank.")
    requirement: str = Field("", title="Requirement")
    priority: str = Field("Must Have", title="Priority")
    source: str = Field("", title="Source")


class MethodologyRow(TableRow):
    phase: str = Field("", title="Phase")
    activities: str = Field("", title="Activities")
    outputs: str = Field("", title="Outputs")


class ToolRow(TableRow):
    tool: str = Field("", title="Tool / Platform")
    purpose: str = Field("", title="Purpose")
    provided_by: str = Field("SonaMation", title="Provided By")


class TechniqueRow(TableRow):
    technique: str = Field("", title="Technique / Procedure")
    how_applied: str = Field("", title="How It Is Applied")


class ScopeRow(TableRow):
    id: str = Field("", title="ID", description="Assigned (S-01, S-02, ...) when blank.")
    workstream: str = Field("", title="Workstream")
    item: str = Field("", title="Item")
    status: ScopeStatus = Field("In Scope", title="Status")
    quantity_limit: str = Field("", title="Quantity / Limit")
    tools_techniques: str = Field("", title="Tools / Techniques")
    requirement_ids: str = Field("", title="Req. ID", description="Comma-separated requirement IDs this item covers.")
    acceptance_criteria: str = Field("", title="Acceptance Criteria")
    milestone: str = Field("", title="Milestone")


class GlossaryRow(TableRow):
    term: str = Field("", title="Term")
    definition: str = Field("", title="Definition")


class TeamRow(TableRow):
    side: str = Field("SonaMation", title="Side")
    role: str = Field("", title="Role")
    name: str = Field("", title="Name")
    email: str = Field("", title="Email")
    responsibilities: str = Field("", title="Responsibilities")


class GovernanceRow(TableRow):
    meeting: str = Field("", title="Meeting / Report")
    cadence: str = Field("", title="Cadence")
    participants: str = Field("", title="Participants")
    purpose: str = Field("", title="Purpose")


class TimelineRow(TableRow):
    phase: str = Field("", title="Phase / Milestone")
    start: str = Field("", title="Start")
    end: str = Field("", title="End")
    key_deliverables: str = Field("", title="Key Deliverables")


class RiskRow(TableRow):
    risk: str = Field("", title="Risk")
    likelihood: str = Field("Medium", title="Likelihood")
    impact: str = Field("Medium", title="Impact")
    mitigation: str = Field("", title="Mitigation")
    owner: str = Field("", title="Owner")


class KpiRow(TableRow):
    kpi: str = Field("", title="KPI")
    type: KpiType = Field("Primary", title="Type")
    definition: str = Field("", title="Definition")
    target: str = Field("", title="Target")


class MilestoneRow(TableRow):
    milestone: str = Field("", title="Milestone")
    deliverables: str = Field("", title="Deliverables")
    start_on_or_before: str = Field("", title="Start On or Before")
    due_on_or_before: str = Field("", title="Due On or Before")
    fee: float = Field(0.0, ge=0, title="Fee")


class AddonRow(TableRow):
    service: str = Field("", title="Service")
    includes: str = Field("", title="Includes")
    cost: float = Field(0.0, ge=0, title="Cost")
    billing: Billing = Field("One Time", title="Billing")
    add_to_total: bool = Field(False, title="Add to Total")


class RateCardRow(TableRow):
    role: str = Field("", title="Role")
    hourly_rate: float = Field(0.0, ge=0, title="Hourly Rate")


class AssumptionRow(TableRow):
    assumption: str = Field("", title="Assumption")


class Party(ApiModel):
    company: str = ""
    contact: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""


class ProposalDocument(ApiModel):
    """A complete proposal / SOW. Start from ``GET /proposals/default``."""

    _TABLES: ClassVar[dict[str, type[TableRow]]] = {
        "objectives": ObjectiveRow,
        "requirements": RequirementRow,
        "methodology": MethodologyRow,
        "tools": ToolRow,
        "techniques": TechniqueRow,
        "glossary": GlossaryRow,
        "scope": ScopeRow,
        "assumptions": AssumptionRow,
        "team": TeamRow,
        "governance": GovernanceRow,
        "timeline": TimelineRow,
        "risks": RiskRow,
        "kpis": KpiRow,
        "milestones": MilestoneRow,
        "addons": AddonRow,
        "rate_card": RateCardRow,
    }

    schema_version: int = dp.SCHEMA_VERSION
    document_type: DocumentType = "Proposal + Statement of Work"
    title: str = ""
    reference_number: str = ""
    issue_date: str = ""
    effective_date: str = ""
    expiration_date: str = ""
    valid_until: str = ""
    client: Party = Field(default_factory=Party)
    seller: Party = Field(default_factory=Party)
    executive_summary: str = ""
    company_overview: str = ""
    problem_statement: str = ""
    current_state: str = ""
    objectives: list[ObjectiveRow] = Field(default_factory=list)
    requirements: list[RequirementRow] = Field(default_factory=list)
    solution_overview: str = ""
    methodology: list[MethodologyRow] = Field(default_factory=list)
    tools: list[ToolRow] = Field(default_factory=list)
    techniques: list[TechniqueRow] = Field(default_factory=list)
    glossary: list[GlossaryRow] = Field(default_factory=list)
    scope: list[ScopeRow] = Field(default_factory=list)
    assumptions: list[AssumptionRow] = Field(default_factory=list)
    change_process: str = ""
    team: list[TeamRow] = Field(default_factory=list)
    governance: list[GovernanceRow] = Field(default_factory=list)
    timeline: list[TimelineRow] = Field(default_factory=list)
    risks: list[RiskRow] = Field(default_factory=list)
    kpis: list[KpiRow] = Field(default_factory=list)
    acceptance_process: str = ""
    currency: str = Field("USD", min_length=3, max_length=3)
    milestones: list[MilestoneRow] = Field(default_factory=list)
    addons: list[AddonRow] = Field(default_factory=list)
    rate_card: list[RateCardRow] = Field(default_factory=list)
    discount_pct: float = Field(0.0, ge=0, le=100)
    payment_terms: str = ""
    expenses: str = ""
    confidentiality: str = ""
    sections: dict[str, bool] = Field(
        default_factory=dict, description=f"Optional sections to include: {', '.join(dp.OPTIONAL_SECTIONS)}."
    )

    def to_domain(self) -> dict[str, Any]:
        doc = self.model_dump()
        for name in self._TABLES:
            doc[name] = [row.to_row() for row in getattr(self, name)]
        return doc

    @classmethod
    def from_domain(cls, proposal: dict[str, Any]) -> ProposalDocument:
        return cls.model_validate(proposal)

    @model_validator(mode="before")
    @classmethod
    def _accept_domain_rows(cls, data: Any) -> Any:
        """Accept label-keyed domain rows (from_domain) as well as API rows."""
        if not isinstance(data, dict):
            return data
        converted = dict(data)
        for name, row_cls in cls._TABLES.items():
            rows = converted.get(name)
            if isinstance(rows, list):
                converted[name] = [
                    row_cls.from_row(r) if isinstance(r, dict) and any(f.title in r for f in row_cls.model_fields.values()) else r
                    for r in rows
                ]
        return converted


# ---- request / response wrappers ---------------------------------------------


class ProposalRequest(ApiModel):
    proposal: ProposalDocument


class PricingSummary(ApiModel):
    milestone_total: float
    selected_addons_one_time: float
    subtotal: float
    discount_pct: float
    discount: float
    total: float
    recurring: dict[str, float] = Field(description="Recurring add-on totals keyed by billing period.")


class CoverageRow(ApiModel):
    id: str
    requirement: str
    scope_items: str = Field(description="Comma-separated IDs of the scope items that cite this requirement.")
    coverage: Coverage

    @classmethod
    def from_domain(cls, row: dict[str, str]) -> CoverageRow:
        return cls.model_validate(
            {"id": row["ID"], "requirement": row["Requirement"], "scope_items": row["Scope Items"], "coverage": row["Coverage"]}
        )


class ProposalAnalysis(ApiModel):
    """Everything the builder shows alongside the document, in one round trip."""

    pricing: PricingSummary
    coverage: list[CoverageRow]
    scope_by_status: dict[ScopeStatus, list[ScopeRow]]
    warnings: list[str] = Field(description="Gaps a client would ask about. Advisory; they never block generation.")


class WrdImportRequest(ApiModel):
    proposal: ProposalDocument
    wrd: dict[str, list[dict[str, str]]] = Field(description="Requirements Document sections, as exported by that module.")


class JepImportRequest(ApiModel):
    proposal: ProposalDocument
    jep: dict[str, list[dict[str, str]]] = Field(description="Joint Evaluation Plan sections, as exported by that module.")
    prospect_name: str = ""


class AddLibraryItemsRequest(ApiModel):
    proposal: ProposalDocument
    items: list[str] = Field(min_length=1, description="Item names from the scope library.")
    status: ScopeStatus = "In Scope"


class AddLibraryAddonsRequest(ApiModel):
    proposal: ProposalDocument
    services: list[str] = Field(min_length=1, description="Service names from the add-on library.")


class ScopeLibraryItem(ApiModel):
    workstream: str
    item: str
    quantity_limit: str
    tools_techniques: str
    acceptance_criteria: str


class AddonLibraryItem(ApiModel):
    service: str
    includes: str
    cost: float
    billing: Billing


class ProposalLibraries(ApiModel):
    scope: list[ScopeLibraryItem]
    addons: list[AddonLibraryItem]

    @classmethod
    def from_domain(cls) -> ProposalLibraries:
        return cls(
            scope=[
                ScopeLibraryItem(
                    workstream=e["Workstream"],
                    item=e["Item"],
                    quantity_limit=e["Quantity / Limit"],
                    tools_techniques=e["Tools / Techniques"],
                    acceptance_criteria=e["Acceptance Criteria"],
                )
                for e in dp.SCOPE_LIBRARY
            ],
            addons=[
                AddonLibraryItem(service=e["Service"], includes=e["Includes"], cost=e["Cost"], billing=e["Billing"])
                for e in dp.ADDON_LIBRARY
            ],
        )
