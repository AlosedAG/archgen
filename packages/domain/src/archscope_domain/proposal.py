"""Seller's Proposal & Statement of Work — data model, SonaMation defaults,
and the pure computations behind Module 10.

A proposal here is one plain, JSON-serializable ``dict`` (see
:func:`default_proposal` for every key), organized around the three areas
a proposal has to answer:

1. **Technical** — understanding of the problem, objectives, the proposed
   solution, and the specific tools, techniques and procedures used to
   implement it, traced back to the customer's requirements.
2. **Management** — team, governance cadence, timeline, risks, change
   control and acceptance: how SonaMation will run contract performance.
3. **Cost** — milestone fees grouped by workstream, recurring fees, optional
   add-ons, rate card, payment schedule and terms.

Commercial completeness (added after benchmarking a real agency SOW): a
structured executive summary, recurring fees kept apart from one-time
fees, a payment schedule, client vs. vendor responsibilities, an
indicative week-based timeline drawn as a Gantt chart, acceptance
evidence per milestone, a data-quality / known-issues table (required for
migrations) and the subscription-tier assumption. A proposal can only be
marked "Ready to send" when :func:`readiness_issues` finds nothing;
blanks the seller must fill are written ``[[like this]]``.

**Scope** cuts across all three and is the part clients most often get
wrong, so it's modeled as one explicit list of scope items, each tagged
with a :data:`SCOPE_STATUSES` value. Everything a client might ask for
lands in exactly one bucket — included, excluded, optional add-on, or
client responsibility — and the PDF renders those buckets side by side.

Boilerplate that rarely changes between deals (company overview,
methodology, change-control, acceptance, payment and expense terms) ships
as SonaMation defaults below; per-deal content (requirements, scope,
pricing) starts blank or is imported from the Requirements Document /
Joint Evaluation Plan pages. Kept Streamlit-free so it's unit-testable.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from archscope_domain.sow_clauses import PLACEHOLDER_RE, clause_blanks, default_clauses

SCHEMA_VERSION = 1

DOCUMENT_TYPES = ["Proposal + Statement of Work", "Proposal", "Statement of Work"]

SCOPE_IN = "In Scope"
SCOPE_OUT = "Out of Scope"
SCOPE_OPTIONAL = "Optional Add-on"
SCOPE_CLIENT = "Client Responsibility"
SCOPE_STATUSES = [SCOPE_IN, SCOPE_OUT, SCOPE_OPTIONAL, SCOPE_CLIENT]

BILLING_OPTIONS = ["One Time", "Monthly", "Per Unit", "Per Year", "Hourly"]
KPI_TYPES = ["Primary", "Secondary"]

# Recurring fees (retainers, subscriptions) and how many months each period is.
CADENCES = {"Monthly": 1, "Quarterly": 3, "Per Year": 12}
DATA_QUALITY_OWNERS = ["Client", "SonaMation"]
INVOICING_OPTIONS = [
    "Per milestone, on acceptance",
    "Monthly in arrears",
    "Quarterly in advance",
    "50% at start, 50% on completion",
    "On completion",
]
DEPOSIT_TYPES = ["Percent", "Amount"]
STATUS_DRAFT = "Draft"
STATUS_READY = "Ready to send"
STATUSES = [STATUS_DRAFT, STATUS_READY]

# Blanks the seller must fill before sending ("[[cap amount]]") use
# sow_clauses.PLACEHOLDER_RE, shared with the terms.

# Every optional section the builder can switch off. The three core
# volumes (technical, management, cost) and the scope summary are always
# rendered — they're the point of the document.
OPTIONAL_SECTIONS = {
    "executive_summary": "Executive Summary",
    "company_overview": "About SonaMation",
    "glossary": "Glossary of Terms",
    "kpis": "Targeted KPIs",
    "risks": "Risk Management",
    "addons": "Optional Add-on Services Menu",
    "rate_card": "Rate Card (Change Requests)",
    "signatures": "Acceptance & Signatures",
    "responsibilities": "Client & SonaMation Responsibilities",
    "timeline_chart": "Timeline Chart",
    "milestone_acceptance": "Milestone Acceptance Evidence",
    "data_quality": "Data Quality & Known Issues",
    "recurring_fees": "Recurring Fees",
    "tier_assumption": "Subscription-Tier Assumption",
}

# ---- Row templates (column order = table column order everywhere) ----------

BLANK_ROWS: dict[str, dict[str, Any]] = {
    "objectives": {"Objective": "", "Success Measure": ""},
    "requirements": {"ID": "", "Requirement": "", "Priority": "Must Have", "Source": ""},
    "methodology": {"Phase": "", "Activities": "", "Outputs": ""},
    "tools": {"Tool / Platform": "", "Purpose": "", "Provided By": "SonaMation"},
    "techniques": {"Technique / Procedure": "", "How It Is Applied": ""},
    "scope": {
        "ID": "",
        "Workstream": "",
        "Item": "",
        "Status": SCOPE_IN,
        "Quantity / Limit": "",
        "Tools / Techniques": "",
        "Req. ID": "",
        "Acceptance Criteria": "",
        "Milestone": "",
    },
    "glossary": {"Term": "", "Definition": ""},
    "team": {"Side": "SonaMation", "Role": "", "Name": "", "Email": "", "Responsibilities": ""},
    "governance": {"Meeting / Report": "", "Cadence": "", "Participants": "", "Purpose": ""},
    "timeline": {
        "Phase / Milestone": "",
        "Start Week": 0.0,
        "Duration (Weeks)": 0.0,
        "Start": "",
        "End": "",
        "Key Deliverables": "",
    },
    "risks": {"Risk": "", "Likelihood": "Medium", "Impact": "Medium", "Mitigation": "", "Owner": ""},
    "kpis": {"KPI": "", "Type": "Primary", "Definition": "", "Target": ""},
    "milestones": {
        "Milestone": "",
        "Workstream / Phase": "",
        "Deliverables": "",
        "Fee Basis": "",
        "Start On or Before": "",
        "Due On or Before": "",
        "Fee": 0.0,
        "Acceptance Evidence": "",
    },
    "recurring_fees": {"Service": "", "Includes": "", "Amount": 0.0, "Cadence": "Monthly", "Term (Months)": 12.0, "Starts": ""},
    "client_responsibilities": {"Responsibility": ""},
    "vendor_responsibilities": {"Responsibility": ""},
    "data_quality": {"Issue": "", "Risk if Not Resolved": "", "Owner": "Client"},
    "clauses": {"Key": "", "Title": "", "Body": "", "Include": True},
    "addons": {"Service": "", "Includes": "", "Cost": 0.0, "Billing": "One Time", "Add to Total": False},
    "rate_card": {"Role": "", "Hourly Rate": 0.0},
    "assumptions": {"Assumption": ""},
}


def blank_rows(table: str, count: int = 1) -> list[dict[str, Any]]:
    return [dict(BLANK_ROWS[table]) for _ in range(count)]


# ---- SonaMation defaults (the parts that rarely change) --------------------

# SonaMation's side of the project team, pre-filled on every new proposal
# (rows can be edited or deleted; the client's people are added per deal).
DEFAULT_TEAM = [
    {
        "Side": "SonaMation",
        "Role": "Executive Sponsor",
        "Name": "",
        "Email": "",
        "Responsibilities": "Accountable for the engagement's success; the final escalation point. Approves scope "
        "changes and signs off on acceptance with the client's sponsor.",
    },
    {
        "Side": "SonaMation",
        "Role": "Team Lead of Client Delivery",
        "Name": "",
        "Email": "",
        "Responsibilities": "Owns day-to-day delivery: plans the work, leads the implementation team, runs the "
        "status meetings, manages risks and reports progress to the client.",
    },
    {
        "Side": "SonaMation",
        "Role": "Onboarding Lead",
        "Name": "",
        "Email": "",
        "Responsibilities": "Runs kickoff and onboarding: collects access, schedules discovery and training "
        "sessions, and is the client's first point of contact during setup.",
    },
    {"Side": "Client", "Role": "", "Name": "", "Email": "", "Responsibilities": ""},
]

DEFAULT_COMPANY_OVERVIEW = (
    "SonaMation is a HubSpot Solutions Partner focused on revenue-operations architecture: CRM data "
    "models, sales and marketing automation, integrations, and the documentation that keeps them "
    "maintainable. Every engagement follows the same requirements-first method — requirements are "
    "written down and agreed before anything is built, and every deliverable is traced back to a "
    "requirement and signed off against written acceptance criteria."
)

DEFAULT_METHODOLOGY = [
    {
        "Phase": "1. Discovery & Requirements",
        "Activities": "Stakeholder interviews, current-state portal audit, written requirements, joint evaluation plan",
        "Outputs": "Written Requirements Document, audit findings, signed-off scope",
    },
    {
        "Phase": "2. Architecture & Design",
        "Activities": "Object model, property data dictionary, associations, pipelines, naming conventions",
        "Outputs": "Architecture blueprint and diagram",
    },
    {
        "Phase": "3. Build & Configure",
        "Activities": "Configuration in a sandbox or controlled portal, integrations, automation",
        "Outputs": "Configured solution, build log",
    },
    {
        "Phase": "4. Test & Accept",
        "Activities": "Internal QA, then customer UAT against each requirement's acceptance criteria",
        "Outputs": "Test Case Document, UAT sign-off",
    },
    {
        "Phase": "5. Launch & Enable",
        "Activities": "Go-live, user training, hand-off documentation, hypercare",
        "Outputs": "Documentation pack, training recording",
    },
]

DEFAULT_TOOLS = [
    {"Tool / Platform": "HubSpot (customer portal)", "Purpose": "System being configured", "Provided By": "Client"},
    {"Tool / Platform": "HubSpot sandbox", "Purpose": "Build and test without touching live data", "Provided By": "Client"},
    {
        "Tool / Platform": "ArchitectureScope",
        "Purpose": "Read-only portal audit, blueprint, documentation, diagrams",
        "Provided By": "SonaMation",
    },
    {
        "Tool / Platform": "Shared project workspace",
        "Purpose": "Status reporting, decisions log, file exchange",
        "Provided By": "SonaMation",
    },
]

DEFAULT_TECHNIQUES = [
    {
        "Technique / Procedure": "Requirements traceability",
        "How It Is Applied": "Every scope item cites the requirement it satisfies; nothing is built without one.",
    },
    {
        "Technique / Procedure": "Read-only audit before change",
        "How It Is Applied": "The live portal is audited first so changes are made against a known baseline.",
    },
    {
        "Technique / Procedure": "Sandbox-first configuration",
        "How It Is Applied": "Changes are built and tested in a sandbox before being promoted to production.",
    },
    {
        "Technique / Procedure": "Two-round testing (QA, then UAT)",
        "How It Is Applied": "SonaMation tests internally first; the client then accepts against written criteria.",
    },
]

DEFAULT_GOVERNANCE = [
    {
        "Meeting / Report": "Kickoff",
        "Cadence": "Once",
        "Participants": "Both teams",
        "Purpose": "Confirm scope, roles, timeline, access",
    },
    {
        "Meeting / Report": "Status call",
        "Cadence": "Weekly",
        "Participants": "Project leads",
        "Purpose": "Progress, blockers, decisions needed",
    },
    {
        "Meeting / Report": "Written status report",
        "Cadence": "Weekly",
        "Participants": "Sponsor, project leads",
        "Purpose": "Progress against milestones, risks, open change requests",
    },
    {
        "Meeting / Report": "Steering review",
        "Cadence": "Per milestone",
        "Participants": "Sponsors",
        "Purpose": "Milestone acceptance, scope and budget decisions",
    },
]

DEFAULT_ASSUMPTIONS = [
    {"Assumption": "The client provides portal access (Super Admin or equivalent) within 5 business days of kickoff."},
    {"Assumption": "The client names one decision-maker who can approve requirements, scope changes and acceptance."},
    {"Assumption": "Client feedback and UAT results are returned within 5 business days of each request."},
    {"Assumption": "Quantities in the scope table are upper limits; anything beyond them goes through change control."},
]

DEFAULT_CHANGE_PROCESS = (
    "Anything not listed as In Scope in this document is out of scope, even if it is related. To add or "
    "change scope, either party submits a written Change Request describing the need. SonaMation replies "
    "within 3 business days with the impact on schedule and cost (priced from the add-on menu or the rate "
    "card). Work starts only after the client approves the Change Request in writing; approved changes "
    "become part of this SOW."
)

DEFAULT_ACCEPTANCE = (
    "Each milestone is complete when its deliverables meet the acceptance criteria in the scope table. "
    "The client has 5 business days after delivery to accept or to list specific deficiencies against those "
    "criteria; SonaMation will correct listed deficiencies and resubmit. A deliverable not rejected in "
    "writing within that window is deemed accepted."
)

DEFAULT_PAYMENT_TERMS = (
    "As complete and final payment for Services completed, delivered and accepted, the client shall pay "
    "SonaMation the fees in the milestone schedule. Invoices are issued on milestone acceptance and are due "
    "net 30 days. All amounts are in U.S. Dollars."
)

DEFAULT_EXPENSES = (
    "SonaMation bears sole responsibility for all expenses incurred in performing the Services, unless "
    "otherwise agreed in writing by the client. Third-party software licenses and subscriptions are the "
    "client's responsibility unless listed as an included add-on."
)

DEFAULT_CONFIDENTIALITY = (
    "This document and all Services are confidential information of the parties and may not be shared "
    "outside the client's organization without SonaMation's written consent."
)

DEFAULT_CLIENT_RESPONSIBILITIES = [
    {"Responsibility": "Provide Super Admin (or equivalent) access to HubSpot and to every system being integrated."},
    {"Responsibility": "Name one decision-maker who approves requirements, scope changes and acceptance."},
    {"Responsibility": "Supply source-data exports, field definitions and sample records for any import or migration."},
    {"Responsibility": "Make subject-matter experts available and return feedback and UAT results within 5 business days."},
    {"Responsibility": "Keep the HubSpot subscription active at the tier this SOW assumes."},
]

DEFAULT_VENDOR_RESPONSIBILITIES = [
    {"Responsibility": "Deliver every In Scope item up to its stated limit and acceptance criteria."},
    {"Responsibility": "Build and test in a sandbox or controlled environment before changing production."},
    {"Responsibility": "Run internal QA before anything is handed to the client for UAT."},
    {"Responsibility": "Report progress, risks and decisions needed every week."},
    {"Responsibility": "Hand over documentation for everything delivered."},
]

DEFAULT_TIER_ASSUMPTION = (
    "This design assumes the client's current HubSpot subscription: [[HubSpot hubs and tiers, e.g. Sales Hub "
    "Professional]]. Some features depend on the subscription tier. If a feature described in this SOW is not "
    "available on that tier, SonaMation will propose a revised design, or the client may change their "
    "subscription; either goes through the Change Request process and may affect the schedule and fees."
)

DEFAULT_PAYMENT_SCHEDULE: dict[str, Any] = {
    "deposit_type": "Percent",
    "deposit_value": 0.0,
    "invoicing": "",
    "due_terms": "",
    "notes": "",
}

DEFAULT_RATE_CARD = [
    {"Role": "Solutions Architect", "Hourly Rate": 175.0},
    {"Role": "HubSpot Consultant", "Hourly Rate": 150.0},
    {"Role": "Developer / Integrations", "Hourly Rate": 165.0},
]


# ---- Preset libraries (a starting menu; every value is editable) ----------
#
# Clients usually don't know what they *can* ask for. These presets give the
# seller a menu of common HubSpot deliverables, each already phrased as a
# bounded item (quantity limit + acceptance criteria), so the scope table
# starts concrete instead of vague.

SCOPE_LIBRARY: list[dict[str, str]] = [
    {
        "Workstream": "Discovery",
        "Item": "Current-state portal audit",
        "Quantity / Limit": "1 portal",
        "Tools / Techniques": "ArchitectureScope Portal Auditor (read-only)",
        "Acceptance Criteria": "Audit report delivered and reviewed with client",
    },
    {
        "Workstream": "Discovery",
        "Item": "Written Requirements Document",
        "Quantity / Limit": "Up to 3 workshops",
        "Tools / Techniques": "Stakeholder interviews, WRD template",
        "Acceptance Criteria": "WRD signed off by client decision-maker",
    },
    {
        "Workstream": "Architecture",
        "Item": "Data model & architecture blueprint",
        "Quantity / Limit": "Up to 2 custom objects",
        "Tools / Techniques": "ArchitectureScope Architecture Generator + Diagram",
        "Acceptance Criteria": "Blueprint approved by client",
    },
    {
        "Workstream": "Configuration",
        "Item": "Custom properties",
        "Quantity / Limit": "Up to 50 properties",
        "Tools / Techniques": "HubSpot property settings, data dictionary",
        "Acceptance Criteria": "Properties match approved data dictionary",
    },
    {
        "Workstream": "Configuration",
        "Item": "Deal / ticket pipelines",
        "Quantity / Limit": "Up to 2 pipelines, 8 stages each",
        "Tools / Techniques": "HubSpot pipeline settings",
        "Acceptance Criteria": "Stages and required fields match blueprint",
    },
    {
        "Workstream": "Automation",
        "Item": "Workflows",
        "Quantity / Limit": "Up to 10 workflows",
        "Tools / Techniques": "HubSpot Workflows, overwrite-risk review",
        "Acceptance Criteria": "Each workflow passes its QA and UAT test case",
    },
    {
        "Workstream": "Automation",
        "Item": "Lead scoring model",
        "Quantity / Limit": "1 model",
        "Tools / Techniques": "HubSpot lead scoring, buyer persona",
        "Acceptance Criteria": "Scores calculated on test contacts as specified",
    },
    {
        "Workstream": "Marketing",
        "Item": "Campaign build (landing page, form, thank-you page, auto-response email)",
        "Quantity / Limit": "1 campaign",
        "Tools / Techniques": "HubSpot Marketing Hub",
        "Acceptance Criteria": "Campaign assets live and test submission tracked end to end",
    },
    {
        "Workstream": "Integration",
        "Item": "Native integration setup",
        "Quantity / Limit": "1 integration, up to 3 synced objects",
        "Tools / Techniques": "HubSpot App Marketplace / Data Sync",
        "Acceptance Criteria": "Records sync in both directions on test data",
    },
    {
        "Workstream": "Data",
        "Item": "Data import / migration",
        "Quantity / Limit": "Up to 10,000 records, 3 objects",
        "Tools / Techniques": "HubSpot import tool, field mapping sheet",
        "Acceptance Criteria": "Record counts reconcile with source file",
    },
    {
        "Workstream": "Reporting",
        "Item": "Dashboards & reports",
        "Quantity / Limit": "Up to 2 dashboards, 10 reports",
        "Tools / Techniques": "HubSpot reporting",
        "Acceptance Criteria": "Reports match agreed definitions",
    },
    {
        "Workstream": "Enablement",
        "Item": "User training",
        "Quantity / Limit": "2 live sessions, recorded",
        "Tools / Techniques": "Video call, training guide",
        "Acceptance Criteria": "Sessions delivered and recordings shared",
    },
    {
        "Workstream": "Enablement",
        "Item": "Hand-off documentation pack",
        "Quantity / Limit": "1 pack",
        "Tools / Techniques": "ArchitectureScope Documentation Generator",
        "Acceptance Criteria": "Documentation delivered for all in-scope items",
    },
    {
        "Workstream": "Support",
        "Item": "Post-launch hypercare",
        "Quantity / Limit": "2 weeks",
        "Tools / Techniques": "Shared support channel",
        "Acceptance Criteria": "Hypercare period completed",
    },
]

# Based on the "Additional Services Menu" in the SOW example; the prices are
# placeholders to overwrite with SonaMation's own.
ADDON_LIBRARY: list[dict[str, Any]] = [
    {
        "Service": "Marketing Automation Platform Setup",
        "Includes": "Portal setup, domains, tracking code, email settings",
        "Cost": 5000.0,
        "Billing": "One Time",
    },
    {
        "Service": "Campaign Development",
        "Includes": "Premium content piece, landing page, form, auto-responder, 2 CTAs",
        "Cost": 4500.0,
        "Billing": "One Time",
    },
    {
        "Service": "Lead Scoring Setup",
        "Includes": "Basic rules and paths, smart lists, notifications and alerts",
        "Cost": 3500.0,
        "Billing": "One Time",
    },
    {
        "Service": "Buyer Persona Development",
        "Includes": "Persona workshops and documented personas",
        "Cost": 2500.0,
        "Billing": "One Time",
    },
    {
        "Service": "SEO Site Audit & Optimization",
        "Includes": "Technical SEO audit and on-page fixes",
        "Cost": 2500.0,
        "Billing": "One Time",
    },
    {
        "Service": "Site Conversion Path Optimization",
        "Includes": "Conversion path review and improvements",
        "Cost": 4500.0,
        "Billing": "One Time",
    },
    {"Service": "Premium Content Piece", "Includes": "One gated content asset", "Cost": 2500.0, "Billing": "One Time"},
    {
        "Service": "Lead Intelligence (1,000 contacts)",
        "Includes": "Third-party enrichment for segmentation; $0.25 per additional contact",
        "Cost": 500.0,
        "Billing": "One Time",
    },
    {
        "Service": "Marketing Support Team",
        "Includes": "Unlimited chat, 1 hour phone support per month, bi-weekly training webinars; 12-month term",
        "Cost": 500.0,
        "Billing": "Monthly",
    },
    {
        "Service": "Quarterly Assessment",
        "Includes": "Quarterly portal health review and recommendations",
        "Cost": 2500.0,
        "Billing": "Per Year",
    },
]


def add_library_items(proposal: dict[str, Any], items: list[str], status: str = SCOPE_IN) -> dict[str, Any]:
    """Append the named :data:`SCOPE_LIBRARY` items to the scope table (skipping any already in it)."""
    p = copy.deepcopy(proposal)
    by_name = {entry["Item"]: entry for entry in SCOPE_LIBRARY}
    scope = nonblank(p.get("scope", []), "Item")
    have = {_same_text(s.get("Item")) for s in scope}
    for name in items:
        if name in by_name and _same_text(name) not in have:
            scope.append({**BLANK_ROWS["scope"], **by_name[name], "Status": status})
            have.add(_same_text(name))
    p["scope"] = number_scope_items(scope)
    return p


def add_library_addons(proposal: dict[str, Any], services: list[str]) -> dict[str, Any]:
    """Append the named :data:`ADDON_LIBRARY` services to the add-on menu,
    and list each one in the scope table as an Optional Add-on so it shows
    up in "Scope at a Glance" with its price."""
    p = copy.deepcopy(proposal)
    by_name = {entry["Service"]: entry for entry in ADDON_LIBRARY}
    addons = nonblank(p.get("addons", []), "Service")
    scope = nonblank(p.get("scope", []), "Item")
    existing_scope = {_same_text(s.get("Item")) for s in scope}
    existing_addons = {_same_text(a.get("Service")) for a in addons}
    for name in services:
        if name not in by_name:
            continue
        if _same_text(name) not in existing_addons:
            addons.append({**BLANK_ROWS["addons"], **by_name[name]})
            existing_addons.add(_same_text(name))
        if _same_text(name) not in existing_scope:
            existing_scope.add(_same_text(name))
            scope.append({**BLANK_ROWS["scope"], "Workstream": "Add-on", "Item": name, "Status": SCOPE_OPTIONAL})
    p["addons"] = addons
    p["scope"] = number_scope_items(scope)
    return p


def default_proposal() -> dict[str, Any]:
    """A fresh proposal: SonaMation boilerplate filled in, per-deal fields blank."""
    return {
        "schema_version": SCHEMA_VERSION,
        # ---- Front matter ----
        "document_type": DOCUMENT_TYPES[0],
        "title": "HubSpot Implementation",
        "reference_number": "",
        "issue_date": "",
        "effective_date": "",
        "expiration_date": "",
        "valid_until": "",
        "client": {"company": "", "contact": "", "address": "", "phone": "", "email": ""},
        "seller": {"company": "SonaMation", "contact": "", "address": "", "phone": "", "email": ""},
        "status": STATUS_DRAFT,
        # None = follow the scope (a scope item mentions a migration / import); True / False = set by hand.
        "is_migration": None,
        "executive_summary": "",
        "exec_key_risks": "",
        "exec_dependencies": "",
        "company_overview": DEFAULT_COMPANY_OVERVIEW,
        # ---- Volume I: Technical ----
        "problem_statement": "",
        "current_state": "",
        "objectives": blank_rows("objectives", 2),
        "requirements": blank_rows("requirements", 3),
        "solution_overview": "",
        "methodology": copy.deepcopy(DEFAULT_METHODOLOGY),
        "tools": copy.deepcopy(DEFAULT_TOOLS),
        "techniques": copy.deepcopy(DEFAULT_TECHNIQUES),
        "glossary": blank_rows("glossary", 1),
        # ---- Scope ----
        "scope": blank_rows("scope", 3),
        "assumptions": copy.deepcopy(DEFAULT_ASSUMPTIONS),
        "tier_assumption": DEFAULT_TIER_ASSUMPTION,
        "data_quality": blank_rows("data_quality", 1),
        "change_process": DEFAULT_CHANGE_PROCESS,
        # ---- Volume II: Management ----
        "team": copy.deepcopy(DEFAULT_TEAM),
        "client_responsibilities": copy.deepcopy(DEFAULT_CLIENT_RESPONSIBILITIES),
        "vendor_responsibilities": copy.deepcopy(DEFAULT_VENDOR_RESPONSIBILITIES),
        "governance": copy.deepcopy(DEFAULT_GOVERNANCE),
        "timeline": blank_rows("timeline", 3),
        "timeline_buffer_weeks": 2.0,
        "timeline_buffer_label": "Validation & buffer",
        "risks": blank_rows("risks", 1),
        "kpis": blank_rows("kpis", 1),
        "acceptance_process": DEFAULT_ACCEPTANCE,
        # ---- Volume III: Cost ----
        "currency": "USD",
        "milestones": blank_rows("milestones", 3),
        "recurring_fees": [],
        "addons": blank_rows("addons", 1),
        "rate_card": copy.deepcopy(DEFAULT_RATE_CARD),
        "discount_pct": 0.0,
        "payment_schedule": copy.deepcopy(DEFAULT_PAYMENT_SCHEDULE),
        "payment_terms": DEFAULT_PAYMENT_TERMS,
        "expenses": DEFAULT_EXPENSES,
        "confidentiality": DEFAULT_CONFIDENTIALITY,
        # ---- Terms (a copy of the firm's clause library; see sow_clauses) ----
        "clauses": default_clauses(),
        # ---- Layout ----
        "sections": {key: True for key in OPTIONAL_SECTIONS},
    }


# ---- Helpers ----------------------------------------------------------------


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN from a DataFrame
        return ""
    return str(value).strip()


def to_float(value: Any) -> float:
    """Lenient money parser: accepts numbers, ``"$1,500.00"``, blanks."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return 0.0 if value != value else float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y", "x"}
    return bool(value) and value == value


def format_money(amount: float, currency: str = "USD") -> str:
    symbol = "$" if currency.upper() in {"USD", "CAD", "AUD", "MXN"} else ""
    sign = "-" if amount < 0 else ""
    text = f"{sign}{symbol}{abs(amount):,.2f}"
    return text if symbol else f"{text} {currency}"


def nonblank(rows: list[dict[str, Any]], *columns: str) -> list[dict[str, Any]]:
    """Rows where at least one of ``columns`` (default: any column) has text."""
    kept = []
    for row in rows or []:
        keys = columns or tuple(row.keys())
        if any(_text(row.get(c)) for c in keys):
            kept.append(row)
    return kept


_ID_RE = re.compile(r"^\s*([A-Za-z]+)\s*-\s*0*(\d+)\s*$")


def id_key(value: Any) -> str:
    """Comparable form of an item ID, so "R-01", "r-1" and "R-1" are the same."""
    text = _text(value)
    m = _ID_RE.match(text)
    return f"{m.group(1).upper()}-{int(m.group(2))}" if m else text.lower()


def _number_rows(rows: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    """Give every row without an ID the next free ``<prefix>-N`` (R-1, R-2…),
    after the numbers already used, so existing references never change."""
    used = {int(m.group(2)) for r in rows if (m := _ID_RE.match(_text(r.get("ID")))) and m.group(1).upper() == prefix}
    n = 0
    out = []
    for row in rows:
        row = dict(row)
        if not _text(row.get("ID")):
            n += 1
            while n in used:
                n += 1
            row["ID"] = f"{prefix}-{n}"
            used.add(n)
        out.append(row)
    return out


def number_scope_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give every scope item without an ID a stable ``S-N`` one so the
    client can cite it in a change request ("is S-7 included?")."""
    return _number_rows(rows, "S")


def number_requirements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give every requirement without an ID a stable ``R-N`` one."""
    return _number_rows(rows, "R")


def scope_by_status(proposal: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Scope items grouped into the four :data:`SCOPE_STATUSES` buckets
    (always all four keys, in that order). Unknown statuses count as In
    Scope rather than silently disappearing from the document."""
    groups: dict[str, list[dict[str, Any]]] = {status: [] for status in SCOPE_STATUSES}
    for row in number_scope_items(nonblank(proposal.get("scope", []), "Item")):
        status = _text(row.get("Status"))
        groups[status if status in groups else SCOPE_IN].append(row)
    return groups


COVERAGE_COVERED = "Covered"
COVERAGE_NONE = "Not covered"
COVERAGE_LABELS = {
    SCOPE_IN: COVERAGE_COVERED,
    SCOPE_OPTIONAL: "Available as add-on",
    SCOPE_CLIENT: "Client responsibility",
    SCOPE_OUT: "Excluded",
}


def requirement_coverage(proposal: dict[str, Any]) -> list[dict[str, str]]:
    """One row per requirement: which scope items cite it (via their
    "Req. ID" column) and what that means for the client.

    A requirement is only a gap ("Not covered") when *no* scope item cites
    it: it has been silently dropped. One cited only by an Out of Scope,
    Optional Add-on, or Client Responsibility item has been dealt with
    explicitly, so it gets that label instead of a warning. IDs match
    case-insensitively and ignoring leading zeros ("r-01" cites "R-1")."""
    requirements = number_requirements(nonblank(proposal.get("requirements", []), "Requirement"))
    scope = number_scope_items(nonblank(proposal.get("scope", []), "Item"))
    rows = []
    for req in requirements:
        rid = _text(req.get("ID"))
        linked = [s for s in scope if rid and id_key(rid) in [id_key(part) for part in _text(s.get("Req. ID")).split(",")]]
        statuses = {_text(s.get("Status")) or SCOPE_IN for s in linked}
        coverage = COVERAGE_NONE
        for status in (SCOPE_IN, SCOPE_OPTIONAL, SCOPE_CLIENT, SCOPE_OUT):
            if status in statuses:
                coverage = COVERAGE_LABELS[status]
                break
        rows.append(
            {
                "ID": rid,
                "Requirement": _text(req.get("Requirement")),
                "Scope Items": ", ".join(_text(s.get("ID")) for s in linked) or "-",
                "Coverage": coverage,
            }
        )
    return rows


def workstream_fees(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    """Milestone fees grouped by their "Workstream / Phase" (in order of first
    appearance; milestones without one fall under "General"), each with the
    fee bases of its milestones."""
    groups: dict[str, dict[str, Any]] = {}
    for m in nonblank(proposal.get("milestones", []), "Milestone"):
        name = _text(m.get("Workstream / Phase")) or "General"
        g = groups.setdefault(name, {"workstream": name, "fee": 0.0, "fee_basis": [], "milestones": []})
        g["fee"] += to_float(m.get("Fee"))
        g["milestones"].append(_text(m.get("Milestone")))
        basis = _text(m.get("Fee Basis"))
        if basis and basis not in g["fee_basis"]:
            g["fee_basis"].append(basis)
    return [{**g, "fee_basis": "; ".join(g["fee_basis"])} for g in groups.values()]


def recurring_rows(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    """The recurring fees, with a known cadence and a term in whole months."""
    rows = []
    for r in nonblank(proposal.get("recurring_fees", []), "Service"):
        cadence = _text(r.get("Cadence"))
        rows.append(
            {
                **r,
                "Cadence": cadence if cadence in CADENCES else "Monthly",
                "Amount": to_float(r.get("Amount")),
                "Term (Months)": max(0.0, to_float(r.get("Term (Months)"))),
            }
        )
    return rows


def pricing_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    """Totals for the cost volume. One-time and recurring money are always
    totalled separately (a monthly fee isn't comparable to a one-time fee,
    so they're never summed together):

    - one-time: milestone fees plus one-time add-ons flagged "Add to Total",
      less the discount;
    - recurring: the recurring fees plus recurring add-ons flagged "Add to
      Total", per billing period, and what the recurring fees come to over
      their terms."""
    milestones = nonblank(proposal.get("milestones", []), "Milestone")
    milestone_total = sum(to_float(m.get("Fee")) for m in milestones)

    selected_one_time = 0.0
    recurring: dict[str, float] = {}
    for addon in nonblank(proposal.get("addons", []), "Service"):
        if not to_bool(addon.get("Add to Total")):
            continue
        cost = to_float(addon.get("Cost"))
        billing = _text(addon.get("Billing")) or "One Time"
        if billing == "One Time":
            selected_one_time += cost
        else:
            recurring[billing] = recurring.get(billing, 0.0) + cost

    term_total = 0.0
    for r in recurring_rows(proposal):
        recurring[r["Cadence"]] = recurring.get(r["Cadence"], 0.0) + r["Amount"]
        term_total += r["Amount"] * (r["Term (Months)"] / CADENCES[r["Cadence"]])

    subtotal = milestone_total + selected_one_time
    discount_pct = max(0.0, min(100.0, to_float(proposal.get("discount_pct"))))
    discount = round(subtotal * discount_pct / 100, 2)
    return {
        "milestone_total": milestone_total,
        "selected_addons_one_time": selected_one_time,
        "subtotal": subtotal,
        "discount_pct": discount_pct,
        "discount": discount,
        "total": subtotal - discount,
        "recurring": recurring,
        "recurring_term_total": round(term_total, 2),
        "workstreams": workstream_fees(proposal),
    }


# ---- Timeline (indicative, in weeks) ----------------------------------------


def timeline_chart(proposal: dict[str, Any]) -> dict[str, Any]:
    """The schedule as Gantt bars, in weeks from 1. A phase without a start
    week starts when the phases before it end; phases may overlap. The
    buffer / validation period follows the last phase. Phases without a
    duration aren't charted."""
    bars: list[dict[str, Any]] = []
    cursor = 1.0  # the first week after everything charted so far
    for row in nonblank(proposal.get("timeline", []), "Phase / Milestone"):
        weeks = to_float(row.get("Duration (Weeks)"))
        if weeks <= 0:
            continue
        start = to_float(row.get("Start Week")) or cursor
        bars.append({"Phase": _text(row.get("Phase / Milestone")), "Start": start, "Weeks": weeks, "Buffer": False})
        cursor = max(cursor, start + weeks)
    buffer = to_float(proposal.get("timeline_buffer_weeks"))
    if bars and buffer > 0:
        label = _text(proposal.get("timeline_buffer_label")) or "Validation & buffer"
        bars.append({"Phase": label, "Start": cursor, "Weeks": buffer, "Buffer": True})
        cursor += buffer
    return {"bars": bars, "total_weeks": cursor - 1}


# ---- Migration projects, payment schedule, readiness --------------------------

_MIGRATION_RE = re.compile(r"migrat|\bimport", re.IGNORECASE)


def migration_scope_items(proposal: dict[str, Any]) -> list[str]:
    """IDs of In Scope / add-on items that mention a migration or import."""
    groups = scope_by_status(proposal)
    return [
        _text(s.get("ID"))
        for s in groups[SCOPE_IN] + groups[SCOPE_OPTIONAL]
        if _MIGRATION_RE.search(f"{_text(s.get('Workstream'))} {_text(s.get('Item'))}")
    ]


def is_migration(proposal: dict[str, Any]) -> bool:
    """Set by hand, or else suggested by the scope."""
    value = proposal.get("is_migration")
    return value if isinstance(value, bool) else bool(migration_scope_items(proposal))


def payment_schedule_present(proposal: dict[str, Any]) -> bool:
    schedule = proposal.get("payment_schedule") or {}
    return bool(_text(schedule.get("invoicing")) and _text(schedule.get("due_terms")))


# Which fields belong to each switchable section (a switched-off section's
# blanks don't hold up sending), and how to name fields in messages.
_SECTION_FIELDS = {
    "executive_summary": ("executive_summary", "exec_key_risks", "exec_dependencies"),
    "company_overview": ("company_overview",),
    "glossary": ("glossary",),
    "kpis": ("kpis",),
    "risks": ("risks",),
    "addons": ("addons",),
    "rate_card": ("rate_card",),
    "responsibilities": ("client_responsibilities", "vendor_responsibilities"),
    "data_quality": ("data_quality",),
    "recurring_fees": ("recurring_fees",),
    "tier_assumption": ("tier_assumption",),
}
_FIELD_LABELS = {
    "executive_summary": "Executive summary",
    "exec_key_risks": "Executive summary (key risks)",
    "exec_dependencies": "Executive summary (what delivery depends on)",
    "tier_assumption": "Subscription-tier assumption",
    "client_responsibilities": "Client responsibilities",
    "vendor_responsibilities": "SonaMation responsibilities",
    "data_quality": "Data quality & known issues",
    "payment_schedule": "Payment schedule",
    "payment_terms": "Payment terms",
}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def unfilled_placeholders(proposal: dict[str, Any]) -> dict[str, list[str]]:
    """``[[blank]]`` markers still in the document, by field (sections that
    are switched off are skipped)."""
    sections = proposal.get("sections") or {}
    skip = {f for key, fields in _SECTION_FIELDS.items() if sections.get(key) is False for f in fields}
    found: dict[str, list[str]] = {}
    for key, value in proposal.items():
        if key in skip or key in ("sections", "status", "clauses"):  # clauses: see clause_blanks
            continue
        for text in _strings(value):
            for blank in PLACEHOLDER_RE.findall(text):
                label = _FIELD_LABELS.get(key, key.replace("_", " ").capitalize())
                if f"[[{blank}]]" not in found.setdefault(label, []):
                    found[label].append(f"[[{blank}]]")
    return found


def readiness_issues(proposal: dict[str, Any]) -> list[str]:
    """What stops the SOW from being marked "Ready to send". Unlike
    :func:`validate`'s warnings, every one of these must be fixed."""
    issues: list[str] = []
    if not payment_schedule_present(proposal):
        issues.append("Payment schedule: choose how invoices are triggered and the due terms (e.g. Net 30).")
    if is_migration(proposal) and not nonblank(proposal.get("data_quality", []), "Issue"):
        issues.append(
            "This project includes a data migration: list at least one known data-quality issue, the risk if it "
            "isn't resolved, and who owns it."
        )
    for label, blanks in unfilled_placeholders(proposal).items():
        issues.append(f"{label}: fill in {', '.join(blanks)}.")
    for title, blanks in clause_blanks(proposal).items():
        issues.append(f"Terms - {title}: fill in {', '.join(blanks)}.")
    return issues


def is_ready(proposal: dict[str, Any]) -> bool:
    """Marked "Ready to send" and nothing is holding it up."""
    return _text(proposal.get("status")) == STATUS_READY and not readiness_issues(proposal)


def validate(proposal: dict[str, Any]) -> list[str]:
    """Plain-language warnings shown before generating the PDF. None of
    these block generation — they point at the gaps a client would ask
    about."""
    warnings: list[str] = []
    if not _text(proposal.get("client", {}).get("company")):
        warnings.append("Client company name is blank.")
    if not _text(proposal.get("problem_statement")):
        warnings.append("Technical volume: 'Understanding of the problem' is blank.")
    if not _text(proposal.get("solution_overview")):
        warnings.append("Technical volume: 'Proposed solution' is blank.")
    groups = scope_by_status(proposal)
    if not groups[SCOPE_IN]:
        warnings.append("Scope: nothing is marked In Scope.")
    if not groups[SCOPE_OUT]:
        warnings.append("Scope: nothing is marked Out of Scope — listing exclusions explicitly prevents most scope disputes.")
    missing_criteria = [r["ID"] for r in groups[SCOPE_IN] if not _text(r.get("Acceptance Criteria"))]
    if missing_criteria:
        warnings.append(f"Scope: In Scope items without acceptance criteria: {', '.join(missing_criteria)}.")
    uncovered = [r["ID"] for r in requirement_coverage(proposal) if r["Coverage"] == COVERAGE_NONE]
    if uncovered:
        warnings.append(f"Requirements not addressed by any scope item: {', '.join(uncovered)}.")
    if pricing_summary(proposal)["milestone_total"] <= 0:
        warnings.append("Cost volume: milestone fees total $0.")
    undated = [
        _text(r.get("Phase / Milestone"))
        for r in nonblank(proposal.get("timeline", []), "Phase / Milestone")
        if to_float(r.get("Duration (Weeks)")) <= 0
    ]
    if undated:
        warnings.append(f"Schedule: phases without a duration in weeks aren't on the timeline chart: {', '.join(undated)}.")
    no_evidence = [
        _text(m.get("Milestone"))
        for m in nonblank(proposal.get("milestones", []), "Milestone")
        if not _text(m.get("Acceptance Evidence"))
    ]
    if no_evidence and (proposal.get("sections") or {}).get("milestone_acceptance", True):
        warnings.append(f"Milestones without acceptance evidence: {', '.join(no_evidence)}.")
    return warnings


# ---- Import from the Requirements Document / Joint Evaluation Plan ----------


def _same_text(value: Any) -> str:
    """Comparable form of a cell: case, spacing and punctuation don't make two rows different."""
    return " ".join(re.sub(r"[^\w\s]", " ", _text(value).lower()).split())


def merge_rows(existing: list[dict[str, Any]], new: list[dict[str, Any]], *key_columns: str) -> list[dict[str, Any]]:
    """``existing`` (blank rows dropped) followed by the ``new`` rows it doesn't
    already have, compared on ``key_columns`` — so importing the same
    document twice adds nothing the second time. Duplicates already in
    ``existing`` (left by earlier imports) collapse to their first copy."""
    seen: set[tuple[str, ...]] = set()
    merged = []
    for row in nonblank(existing, *key_columns) + new:
        key = tuple(_same_text(row.get(c)) for c in key_columns)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def _merge_requirements(
    existing: list[dict[str, Any]], new: list[dict[str, Any]], scope: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Requirements merged like :func:`merge_rows` on their text, except that a
    duplicate a scope item already cites by ID is kept, so no "Req. ID"
    reference is left pointing at nothing."""
    cited = {id_key(part) for s in scope for part in _text(s.get("Req. ID")).split(",") if part.strip()}
    seen: set[str] = set()
    merged = []
    for row in number_requirements(nonblank(existing, "Requirement")) + new:
        key = _same_text(row.get("Requirement"))
        if key in seen and id_key(row.get("ID")) not in cited:
            continue
        seen.add(key)
        merged.append(row)
    return number_requirements(merged)


def import_from_wrd(proposal: dict[str, Any], wrd: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """Merge a Written Requirements Document export (``{section title:
    rows}``, as published by the WRD page) into ``proposal``. Blank
    proposal fields are filled; tables are appended to (after dropping the
    proposal's blank placeholder rows), never overwritten, and rows the
    proposal already has are skipped, so importing again adds no duplicates."""
    p = copy.deepcopy(proposal)

    overview = wrd.get("Project Overview", [])
    purpose = next((_text(r.get("Value")) for r in overview if _text(r.get("Field")) == "Purpose"), "")
    if purpose and not _text(p.get("problem_statement")):
        p["problem_statement"] = purpose

    goals = [{"Objective": _text(r.get("Goal")), "Success Measure": ""} for r in wrd.get("Goals", []) if _text(r.get("Goal"))]
    p["objectives"] = merge_rows(p.get("objectives", []), goals, "Objective")

    new_reqs = [
        {"ID": "", "Requirement": _text(r.get("Requirement")), "Priority": "Must Have", "Source": "Requirements Document"}
        for r in wrd.get("Customer Requirements", [])
        if _text(r.get("Requirement"))
    ]
    p["requirements"] = _merge_requirements(p.get("requirements", []), new_reqs, p.get("scope", []))

    terms = [
        {"Term": _text(r.get("Term")), "Definition": _text(r.get("Definition"))}
        for r in wrd.get("Project Definitions", [])
        if _text(r.get("Term"))
    ]
    p["glossary"] = merge_rows(p.get("glossary", []), terms, "Term")

    risks = [
        {**BLANK_ROWS["risks"], "Risk": f"{_text(r.get('Type')) or 'Risk'}: {_text(r.get('Description'))}"}
        for r in wrd.get("Known Challenges or Risks", [])
        if _text(r.get("Description"))
    ]
    p["risks"] = merge_rows(p.get("risks", []), risks, "Risk")

    plan = [
        {
            "Phase / Milestone": _text(r.get("Milestone")),
            "Start": "",
            "End": _text(r.get("Target Date"))[:10],
            "Key Deliverables": _text(r.get("Related Requirement")),
        }
        for r in wrd.get("Project Plan", [])
        if _text(r.get("Milestone"))
    ]
    p["timeline"] = merge_rows(p.get("timeline", []), plan, "Phase / Milestone")

    questions = [
        {"Assumption": f"To be confirmed: {_text(r.get('Question'))}"}
        for r in wrd.get("Open Questions", [])
        if _text(r.get("Question"))
    ]
    p["assumptions"] = merge_rows(p.get("assumptions", []), questions, "Assumption")
    return p


def import_from_jep(proposal: dict[str, Any], jep: dict[str, list[dict[str, str]]], prospect_name: str = "") -> dict[str, Any]:
    """Merge a Joint Evaluation Plan export into ``proposal``: the team
    roster, technical/business needs (as requirements), milestones (as
    timeline) and the partner contact."""
    p = copy.deepcopy(proposal)

    if prospect_name and not _text(p["client"].get("company")):
        p["client"]["company"] = prospect_name

    contact = {_text(r.get("Field")): _text(r.get("Value")) for r in jep.get("Solutions Partner Contact", [])}
    for field, key in (("Contact Name", "contact"), ("Contact Phone", "phone"), ("Contact Email", "email")):
        if contact.get(field) and not _text(p["seller"].get(key)):
            p["seller"][key] = contact[field]

    team = [
        {
            "Side": "Client" if _text(r.get("Side")) == "Prospect" else "SonaMation",
            "Role": _text(r.get("Role")),
            "Name": _text(r.get("Team Member")),
            "Email": _text(r.get("Email")),
            "Responsibilities": "",
        }
        for r in jep.get("Team Members", [])
        if _text(r.get("Team Member"))
    ]
    p["team"] = merge_rows(p.get("team", []), team, "Name", "Role")

    new_reqs = []
    for section, label in (("Technical Needs", "Technical need"), ("Business Needs", "Business need")):
        for r in jep.get(section, []):
            if _text(r.get("Functionality")):
                new_reqs.append(
                    {
                        "ID": "",
                        "Requirement": _text(r.get("Functionality")),
                        "Priority": "Must Have" if to_bool(r.get("Confirmed")) else "To Confirm",
                        "Source": f"Joint Evaluation Plan ({label})",
                    }
                )
    p["requirements"] = _merge_requirements(p.get("requirements", []), new_reqs, p.get("scope", []))

    plan = [
        {
            "Phase / Milestone": _text(r.get("Milestone")),
            "Start": "",
            "End": _text(r.get("Target Date"))[:10],
            "Key Deliverables": _text(r.get("Outcome / Notes")),
        }
        for r in jep.get("Milestones", [])
        if _text(r.get("Milestone"))
    ]
    p["timeline"] = merge_rows(p.get("timeline", []), plan, "Phase / Milestone")

    questions = [
        {"Assumption": f"To be confirmed: {_text(r.get('Question'))}"}
        for r in jep.get("Questions", [])
        if _text(r.get("Question"))
    ]
    p["assumptions"] = merge_rows(p.get("assumptions", []), questions, "Assumption")
    return p


def scope_from_requirements(proposal: dict[str, Any]) -> dict[str, Any]:
    """Draft one In Scope item per requirement that no scope item cites
    yet — a starting point the seller then edits into concrete, limited
    deliverables (quantities, acceptance criteria)."""
    p = copy.deepcopy(proposal)
    p["requirements"] = number_requirements(nonblank(p.get("requirements", []), "Requirement"))
    scope = number_scope_items(nonblank(p.get("scope", []), "Item"))
    cited = {id_key(part) for s in scope for part in _text(s.get("Req. ID")).split(",") if part.strip()}
    for req in p["requirements"]:
        if id_key(req["ID"]) in cited:
            continue
        scope.append({**BLANK_ROWS["scope"], "Item": _text(req.get("Requirement")), "Req. ID": req["ID"]})
    p["scope"] = number_scope_items(scope)
    return p


def responsibilities_from_scope(proposal: dict[str, Any]) -> dict[str, Any]:
    """Add every Client Responsibility scope item to the client's
    responsibilities (skipping ones already listed)."""
    p = copy.deepcopy(proposal)
    new = [{"Responsibility": _text(s.get("Item"))} for s in scope_by_status(p)[SCOPE_CLIENT]]
    p["client_responsibilities"] = merge_rows(p.get("client_responsibilities", []), new, "Responsibility")
    return p


# Typical weeks per methodology phase when drafting the schedule from it.
_PHASE_WEEKS = (2.0, 2.0, 4.0, 2.0, 1.0)


def timeline_from_methodology(proposal: dict[str, Any]) -> dict[str, Any]:
    """When no schedule phase has a duration yet, draft one phase per
    methodology phase with typical durations, back to back (the seller then
    adjusts weeks and overlaps). A schedule that already has durations is
    left alone."""
    p = copy.deepcopy(proposal)
    timeline = nonblank(p.get("timeline", []), "Phase / Milestone")
    if any(to_float(r.get("Duration (Weeks)")) > 0 for r in timeline):
        return p
    start = 1.0
    drafted = []
    for i, phase in enumerate(nonblank(p.get("methodology", []), "Phase")):
        weeks = _PHASE_WEEKS[i] if i < len(_PHASE_WEEKS) else 2.0
        drafted.append(
            {
                **BLANK_ROWS["timeline"],
                "Phase / Milestone": re.sub(r"^\s*\d+[.)]\s*", "", _text(phase.get("Phase"))),
                "Start Week": start,
                "Duration (Weeks)": weeks,
                "Key Deliverables": _text(phase.get("Outputs")),
            }
        )
        start += weeks
    by_name = {_same_text(r.get("Phase / Milestone")): r for r in timeline}
    for row in drafted:
        existing = by_name.get(_same_text(row["Phase / Milestone"]))
        if existing is not None:
            existing.update({"Start Week": row["Start Week"], "Duration (Weeks)": row["Duration (Weeks)"]})
    p["timeline"] = timeline + [r for r in drafted if _same_text(r["Phase / Milestone"]) not in by_name]
    return p


_SEVERITY_RISK = {
    "High": "High: carried into the new setup, it can lose or corrupt records and break automation or reports.",
    "Medium": "Medium: carried into the new setup, it makes reports and segmentation unreliable.",
}


def data_quality_from_findings(proposal: dict[str, Any], findings: list[dict[str, Any]], limit: int = 15) -> dict[str, Any]:
    """Add the Portal Auditor's High and Medium findings as known data-quality
    issues (owned by the client, whose data it is; editable)."""
    p = copy.deepcopy(proposal)
    order = {"High": 0, "Medium": 1}
    picked = sorted(
        (f for f in findings if isinstance(f, dict) and _text(f.get("severity")) in order and _text(f.get("description"))),
        key=lambda f: order[_text(f.get("severity"))],
    )[:limit]
    new = [
        {
            "Issue": _text(f.get("description")),
            "Risk if Not Resolved": _SEVERITY_RISK[_text(f.get("severity"))],
            "Owner": "Client",
        }
        for f in picked
    ]
    p["data_quality"] = merge_rows(p.get("data_quality", []), new, "Issue")
    return p


# ---- JSON round-trip (templates / re-editing) --------------------------------


def to_json(proposal: dict[str, Any]) -> str:
    return json.dumps(proposal, indent=2, default=str)


def from_json(text: str | bytes) -> dict[str, Any]:
    """Load a saved proposal/template. Missing keys (older files, or a
    hand-trimmed template) fall back to :func:`default_proposal` values so
    the builder always has every field it expects."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Proposal file must contain a JSON object.")
    merged = default_proposal()
    for key, value in data.items():
        if key in ("client", "seller", "sections", "payment_schedule") and isinstance(value, dict):
            merged[key].update(value)
        elif key in merged:
            merged[key] = value
    return merged


# What identifies one deal's client; cleared when a proposal is saved as a
# shared template so the next client starts with everything else.
CLIENT_SPECIFIC_FIELDS = ("reference_number", "issue_date", "effective_date", "expiration_date", "valid_until")


def as_saved_template(proposal: dict[str, Any]) -> dict[str, Any]:
    """A filled-in proposal as a reusable template for a similar client:
    keeps nearly everything (requirements, scope, team, pricing, schedule,
    risks, KPIs, all text) and clears only what identifies this client —
    their contact details, the dates and reference number, and the names
    and emails of the client's people (their roles stay)."""
    template = from_json(to_json(proposal))
    template["client"] = {key: "" for key in template.get("client", {})} or copy.deepcopy(default_proposal()["client"])
    for field in CLIENT_SPECIFIC_FIELDS:
        template[field] = ""
    template["status"] = STATUS_DRAFT
    for row in template.get("team", []):
        if _text(row.get("Side")).lower() == "client":
            row["Name"] = ""
            row["Email"] = ""
    return template


def apply_saved_template(template: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Start ``current`` from ``template``: the template's content, with
    this deal's client details, dates and reference number kept."""
    merged = from_json(to_json(template))
    if any(_text(v) for v in current.get("client", {}).values()):
        merged["client"] = copy.deepcopy(current["client"])
    for field in CLIENT_SPECIFIC_FIELDS:
        if _text(current.get(field)):
            merged[field] = current[field]
    return merged


def as_template(proposal: dict[str, Any]) -> dict[str, Any]:
    """Strip deal-specific content, keeping the reusable parts (seller
    details, methodology, tools, techniques, governance, rate card, add-on
    menu, standard terms, section choices) — for "save as template"."""
    template = default_proposal()
    for key in (
        "seller",
        "company_overview",
        "methodology",
        "tools",
        "techniques",
        "governance",
        "assumptions",
        "change_process",
        "acceptance_process",
        "currency",
        "addons",
        "rate_card",
        "payment_terms",
        "payment_schedule",
        "client_responsibilities",
        "vendor_responsibilities",
        "tier_assumption",
        "timeline_buffer_weeks",
        "timeline_buffer_label",
        "expenses",
        "confidentiality",
        "clauses",
        "sections",
        "kpis",
    ):
        template[key] = copy.deepcopy(proposal.get(key, template[key]))
    for addon in template["addons"]:
        addon["Add to Total"] = False
    return template
