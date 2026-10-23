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

from datetime import datetime
from typing import Any, ClassVar, Literal, Self

from pydantic import Field, model_validator

from archscope_domain import proposal as dp

from .base import ApiModel

ScopeStatus = Literal["In Scope", "Out of Scope", "Optional Add-on", "Client Responsibility"]
Billing = Literal["One Time", "Monthly", "Per Unit", "Per Year", "Hourly"]
KpiType = Literal["Primary", "Secondary"]
DocumentType = Literal["Proposal + Statement of Work", "Proposal", "Statement of Work"]
Coverage = Literal["Covered", "Not covered", "Available as add-on", "Client responsibility", "Excluded"]
Cadence = Literal["Monthly", "Quarterly", "Per Year"]
DataQualityOwner = Literal["Client", "SonaMation"]
Status = Literal["Draft", "Ready to send"]
PrefillPart = Literal["responsibilities", "timeline", "data_quality"]


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
    id: str = Field("", title="ID", description="Assigned (R-1, R-2, ...) when blank.")
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
    id: str = Field("", title="ID", description="Assigned (S-1, S-2, ...) when blank.")
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
    start_week: float = Field(
        0.0, ge=0, title="Start Week", description="Week the phase starts (1 = first week); 0 = right after the phases before it."
    )
    duration_weeks: float = Field(0.0, ge=0, title="Duration (Weeks)", description="0 = not on the timeline chart.")
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
    workstream: str = Field("", title="Workstream / Phase", description="Fees are grouped and subtotalled by this.")
    deliverables: str = Field("", title="Deliverables")
    fee_basis: str = Field(
        "", title="Fee Basis", description="What the fee covers (e.g. 'Fixed fee: 2 pipelines, 10 workflows')."
    )
    start_on_or_before: str = Field("", title="Start On or Before")
    due_on_or_before: str = Field("", title="Due On or Before")
    fee: float = Field(0.0, ge=0, title="Fee")
    acceptance_evidence: str = Field(
        "", title="Acceptance Evidence", description="What the client receives to accept the milestone."
    )


class RecurringFeeRow(TableRow):
    service: str = Field("", title="Service")
    includes: str = Field("", title="Includes")
    amount: float = Field(0.0, ge=0, title="Amount", description="Per billing period.")
    cadence: Cadence = Field("Monthly", title="Cadence")
    term_months: float = Field(12.0, ge=0, title="Term (Months)")
    starts: str = Field("", title="Starts")


class ResponsibilityRow(TableRow):
    responsibility: str = Field("", title="Responsibility")


class DataQualityRow(TableRow):
    issue: str = Field("", title="Issue")
    risk_if_not_resolved: str = Field("", title="Risk if Not Resolved")
    owner: DataQualityOwner = Field("Client", title="Owner")


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


class PaymentSchedule(ApiModel):
    deposit_type: Literal["Percent", "Amount"] = "Percent"
    deposit_value: float = Field(0.0, ge=0, description="Percent of the one-time total, or an amount; 0 = no deposit.")
    invoicing: str = Field("", description="What triggers invoices, e.g. 'Per milestone, on acceptance'.")
    due_terms: str = Field("", description="e.g. 'Net 30'.")
    notes: str = ""


class ClauseRow(TableRow):
    """One clause of this SOW's terms (a copy of the firm's library clause, editable here)."""

    key: str = Field("", title="Key", description="The library clause it came from; empty for a clause added to this SOW only.")
    title: str = Field("", title="Title")
    body: str = Field(
        "",
        title="Body",
        description="[[blanks]] are filled per SOW; {{client}}, {{seller}}, {{valid_until}}, {{effective_date}} fill in automatically.",
    )
    include: bool = Field(True, title="Include")


class LibraryClause(ApiModel):
    """A clause of the workspace's standard SOW terms."""

    id: str
    key: str
    title: str
    body: str
    include_by_default: bool


class LibraryClauseIn(ApiModel):
    id: str | None = Field(None, description="Omit for a new clause.")
    key: str = Field(
        "",
        max_length=80,
        pattern=r"^[a-z0-9_]*$",
        description="Kept stable so SOW copies keep matching; made from the title when empty.",
    )
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    include_by_default: bool = True


class LibraryClausesSave(ApiModel):
    clauses: list[LibraryClauseIn] = Field(max_length=100)


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
        "recurring_fees": RecurringFeeRow,
        "client_responsibilities": ResponsibilityRow,
        "vendor_responsibilities": ResponsibilityRow,
        "data_quality": DataQualityRow,
        "clauses": ClauseRow,
    }

    schema_version: int = dp.SCHEMA_VERSION
    status: Status = Field("Draft", description='"Ready to send" only when the readiness checks pass.')
    is_migration: bool | None = Field(None, description="None = suggested from the scope (a migration / import item).")
    document_type: DocumentType = "Proposal + Statement of Work"
    title: str = ""
    reference_number: str = ""
    issue_date: str = ""
    effective_date: str = ""
    expiration_date: str = ""
    valid_until: str = ""
    client: Party = Field(default_factory=Party)
    seller: Party = Field(default_factory=Party)
    executive_summary: str = Field("", description="Plain-language overview: what is being done.")
    exec_key_risks: str = ""
    exec_dependencies: str = Field("", description="What delivery depends on.")
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
    tier_assumption: str = ""
    data_quality: list[DataQualityRow] = Field(default_factory=list)
    change_process: str = ""
    team: list[TeamRow] = Field(default_factory=list)
    client_responsibilities: list[ResponsibilityRow] = Field(default_factory=list)
    vendor_responsibilities: list[ResponsibilityRow] = Field(default_factory=list)
    governance: list[GovernanceRow] = Field(default_factory=list)
    timeline: list[TimelineRow] = Field(default_factory=list)
    timeline_buffer_weeks: float = Field(0.0, ge=0, description="Validation / buffer period after the last phase.")
    timeline_buffer_label: str = "Validation & buffer"
    risks: list[RiskRow] = Field(default_factory=list)
    kpis: list[KpiRow] = Field(default_factory=list)
    acceptance_process: str = ""
    currency: str = Field("USD", min_length=3, max_length=3)
    milestones: list[MilestoneRow] = Field(default_factory=list)
    recurring_fees: list[RecurringFeeRow] = Field(default_factory=list)
    addons: list[AddonRow] = Field(default_factory=list)
    rate_card: list[RateCardRow] = Field(default_factory=list)
    discount_pct: float = Field(0.0, ge=0, le=100)
    payment_schedule: PaymentSchedule = Field(default_factory=PaymentSchedule)
    payment_terms: str = ""
    expenses: str = ""
    confidentiality: str = ""
    clauses: list[ClauseRow] = Field(default_factory=list, description="This SOW's terms, copied from the firm's clause library.")
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


class WorkstreamFee(ApiModel):
    workstream: str
    fee: float
    fee_basis: str
    milestones: list[str]


class PricingSummary(ApiModel):
    milestone_total: float
    selected_addons_one_time: float
    subtotal: float
    discount_pct: float
    discount: float
    total: float = Field(description="The one-time total.")
    recurring: dict[str, float] = Field(description="Recurring fees and selected recurring add-ons, keyed by billing period.")
    recurring_term_total: float = Field(description="What the recurring fees come to over their terms.")
    workstreams: list[WorkstreamFee]


class TimelineBar(ApiModel):
    phase: str
    start: float = Field(description="First week (1-based).")
    weeks: float
    buffer: bool


class TimelineChart(ApiModel):
    bars: list[TimelineBar]
    total_weeks: float


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
    readiness: list[str] = Field(description='What stops the SOW from being marked "Ready to send". Empty = it can be.')
    is_migration: bool = Field(description="Whether this counts as a migration project (set by hand, or from the scope).")
    migration_items: list[str] = Field(description="IDs of scope items that mention a migration or import.")
    timeline: TimelineChart


class PrefillRequest(ApiModel):
    proposal: ProposalDocument
    parts: list[PrefillPart] = Field(min_length=1)
    findings: list[dict[str, Any]] = Field(
        default_factory=list, description="Portal Auditor findings (severity, description), for the data_quality part."
    )


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


# ---- Shared templates ---------------------------------------------------------------------------


class ProposalTemplateSummary(ApiModel):
    """A saved template, as listed in the builder."""

    id: str
    name: str
    description: str = ""
    created_by: str | None = Field(None, description="Name of who saved it.")
    updated_at: datetime
    requirement_count: int = 0
    scope_count: int = 0
    can_delete: bool = False


class ProposalTemplateSave(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=500)
    proposal: ProposalDocument
    replace: bool = Field(False, description="Overwrite a template that already has this name.")


class ProposalTemplateUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
