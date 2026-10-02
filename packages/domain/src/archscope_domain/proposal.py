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
3. **Cost** — milestone fees, optional add-ons, rate card, payment terms.

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
from typing import Any

SCHEMA_VERSION = 1

DOCUMENT_TYPES = ["Proposal + Statement of Work", "Proposal", "Statement of Work"]

SCOPE_IN = "In Scope"
SCOPE_OUT = "Out of Scope"
SCOPE_OPTIONAL = "Optional Add-on"
SCOPE_CLIENT = "Client Responsibility"
SCOPE_STATUSES = [SCOPE_IN, SCOPE_OUT, SCOPE_OPTIONAL, SCOPE_CLIENT]

BILLING_OPTIONS = ["One Time", "Monthly", "Per Unit", "Per Year", "Hourly"]
KPI_TYPES = ["Primary", "Secondary"]

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
    "timeline": {"Phase / Milestone": "", "Start": "", "End": "", "Key Deliverables": ""},
    "risks": {"Risk": "", "Likelihood": "Medium", "Impact": "Medium", "Mitigation": "", "Owner": ""},
    "kpis": {"KPI": "", "Type": "Primary", "Definition": "", "Target": ""},
    "milestones": {"Milestone": "", "Deliverables": "", "Start On or Before": "", "Due On or Before": "", "Fee": 0.0},
    "addons": {"Service": "", "Includes": "", "Cost": 0.0, "Billing": "One Time", "Add to Total": False},
    "rate_card": {"Role": "", "Hourly Rate": 0.0},
    "assumptions": {"Assumption": ""},
}


def blank_rows(table: str, count: int = 1) -> list[dict[str, Any]]:
    return [dict(BLANK_ROWS[table]) for _ in range(count)]


# ---- SonaMation defaults (the parts that rarely change) --------------------

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
    """Append the named :data:`SCOPE_LIBRARY` items to the scope table."""
    p = copy.deepcopy(proposal)
    by_name = {entry["Item"]: entry for entry in SCOPE_LIBRARY}
    scope = nonblank(p.get("scope", []), "Item")
    for name in items:
        if name in by_name:
            scope.append({**BLANK_ROWS["scope"], **by_name[name], "Status": status})
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
    existing_scope = {_text(s.get("Item")).lower() for s in scope}
    for name in services:
        if name not in by_name:
            continue
        addons.append({**BLANK_ROWS["addons"], **by_name[name]})
        if name.lower() not in existing_scope:
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
        "executive_summary": "",
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
        "change_process": DEFAULT_CHANGE_PROCESS,
        # ---- Volume II: Management ----
        "team": blank_rows("team", 2),
        "governance": copy.deepcopy(DEFAULT_GOVERNANCE),
        "timeline": blank_rows("timeline", 3),
        "risks": blank_rows("risks", 1),
        "kpis": blank_rows("kpis", 1),
        "acceptance_process": DEFAULT_ACCEPTANCE,
        # ---- Volume III: Cost ----
        "currency": "USD",
        "milestones": blank_rows("milestones", 3),
        "addons": blank_rows("addons", 1),
        "rate_card": copy.deepcopy(DEFAULT_RATE_CARD),
        "discount_pct": 0.0,
        "payment_terms": DEFAULT_PAYMENT_TERMS,
        "expenses": DEFAULT_EXPENSES,
        "confidentiality": DEFAULT_CONFIDENTIALITY,
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


def number_scope_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give every scope item without an ID a stable ``S-NN`` one so the
    client can cite it in a change request ("is S-07 included?")."""
    used = {_text(r.get("ID")) for r in rows if _text(r.get("ID"))}
    n = 1
    out = []
    for row in rows:
        row = dict(row)
        if not _text(row.get("ID")):
            while f"S-{n:02d}" in used:
                n += 1
            row["ID"] = f"S-{n:02d}"
            used.add(row["ID"])
        out.append(row)
    return out


def number_requirements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used = {_text(r.get("ID")) for r in rows if _text(r.get("ID"))}
    n = 1
    out = []
    for row in rows:
        row = dict(row)
        if not _text(row.get("ID")):
            while f"R-{n:02d}" in used:
                n += 1
            row["ID"] = f"R-{n:02d}"
            used.add(row["ID"])
        out.append(row)
    return out


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
    case-insensitively ("r-01" cites "R-01")."""
    requirements = number_requirements(nonblank(proposal.get("requirements", []), "Requirement"))
    scope = number_scope_items(nonblank(proposal.get("scope", []), "Item"))
    rows = []
    for req in requirements:
        rid = _text(req.get("ID"))
        linked = [
            s for s in scope if rid and rid.lower() in [part.strip().lower() for part in _text(s.get("Req. ID")).split(",")]
        ]
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


def pricing_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    """Totals for the cost volume. Add-ons flagged "Add to Total" are
    included; one-time add-ons join the one-time subtotal, recurring ones
    are reported separately (a monthly fee isn't comparable to a one-time
    fee, so they're never silently summed together)."""
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
    }


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
    return warnings


# ---- Import from the Requirements Document / Joint Evaluation Plan ----------


def import_from_wrd(proposal: dict[str, Any], wrd: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """Merge a Written Requirements Document export (``{section title:
    rows}``, as published by the WRD page) into ``proposal``. Blank
    proposal fields are filled; tables are appended to (after dropping the
    proposal's blank placeholder rows), never overwritten."""
    p = copy.deepcopy(proposal)

    overview = wrd.get("Project Overview", [])
    purpose = next((_text(r.get("Value")) for r in overview if _text(r.get("Field")) == "Purpose"), "")
    if purpose and not _text(p.get("problem_statement")):
        p["problem_statement"] = purpose

    goals = [{"Objective": _text(r.get("Goal")), "Success Measure": ""} for r in wrd.get("Goals", []) if _text(r.get("Goal"))]
    p["objectives"] = nonblank(p.get("objectives", []), "Objective") + goals

    existing_reqs = number_requirements(nonblank(p.get("requirements", []), "Requirement"))
    new_reqs = [
        {"ID": "", "Requirement": _text(r.get("Requirement")), "Priority": "Must Have", "Source": "Requirements Document"}
        for r in wrd.get("Customer Requirements", [])
        if _text(r.get("Requirement"))
    ]
    p["requirements"] = number_requirements(existing_reqs + new_reqs)

    terms = [
        {"Term": _text(r.get("Term")), "Definition": _text(r.get("Definition"))}
        for r in wrd.get("Project Definitions", [])
        if _text(r.get("Term"))
    ]
    p["glossary"] = nonblank(p.get("glossary", []), "Term") + terms

    risks = [
        {**BLANK_ROWS["risks"], "Risk": f"{_text(r.get('Type')) or 'Risk'}: {_text(r.get('Description'))}"}
        for r in wrd.get("Known Challenges or Risks", [])
        if _text(r.get("Description"))
    ]
    p["risks"] = nonblank(p.get("risks", []), "Risk") + risks

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
    p["timeline"] = nonblank(p.get("timeline", []), "Phase / Milestone") + plan

    questions = [
        {"Assumption": f"To be confirmed: {_text(r.get('Question'))}"}
        for r in wrd.get("Open Questions", [])
        if _text(r.get("Question"))
    ]
    p["assumptions"] = nonblank(p.get("assumptions", []), "Assumption") + questions
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
    p["team"] = nonblank(p.get("team", []), "Name", "Role") + team

    existing_reqs = number_requirements(nonblank(p.get("requirements", []), "Requirement"))
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
    p["requirements"] = number_requirements(existing_reqs + new_reqs)

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
    p["timeline"] = nonblank(p.get("timeline", []), "Phase / Milestone") + plan

    questions = [
        {"Assumption": f"To be confirmed: {_text(r.get('Question'))}"}
        for r in jep.get("Questions", [])
        if _text(r.get("Question"))
    ]
    p["assumptions"] = nonblank(p.get("assumptions", []), "Assumption") + questions
    return p


def scope_from_requirements(proposal: dict[str, Any]) -> dict[str, Any]:
    """Draft one In Scope item per requirement that no scope item cites
    yet — a starting point the seller then edits into concrete, limited
    deliverables (quantities, acceptance criteria)."""
    p = copy.deepcopy(proposal)
    p["requirements"] = number_requirements(nonblank(p.get("requirements", []), "Requirement"))
    scope = number_scope_items(nonblank(p.get("scope", []), "Item"))
    cited = {part.strip() for s in scope for part in _text(s.get("Req. ID")).split(",") if part.strip()}
    for req in p["requirements"]:
        if req["ID"] in cited:
            continue
        scope.append({**BLANK_ROWS["scope"], "Item": _text(req.get("Requirement")), "Req. ID": req["ID"]})
    p["scope"] = number_scope_items(scope)
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
        if key in ("client", "seller", "sections") and isinstance(value, dict):
            merged[key].update(value)
        elif key in merged:
            merged[key] = value
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
        "expenses",
        "confidentiality",
        "sections",
        "kpis",
    ):
        template[key] = copy.deepcopy(proposal.get(key, template[key]))
    for addon in template["addons"]:
        addon["Add to Total"] = False
    return template
