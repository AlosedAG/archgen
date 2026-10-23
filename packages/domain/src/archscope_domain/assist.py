"""Context-aware suggestions: the "Fill from earlier steps" / "Suggest"
buttons. The model reads what the project already holds (discovery call
notes, the business analysis, the Requirements Document, the Joint
Evaluation Plan, an applied stage planner) and proposes values for one
page; the merge functions here then fill only what is still blank, so a
suggestion never overwrites what the user typed.

Like :mod:`archscope_domain.discovery`, this module calls an SDK client it
is handed (Anthropic or google-genai) by duck typing and never imports
either SDK.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from archscope_domain import discovery as dd
from archscope_domain import proposal as pp

STAGE_PLANNER = "stage_planner"
PROPOSAL = "proposal"
ARCHITECTURE = "architecture"
PROJECT_TASKS = "project_tasks"
COMPANY_OVERVIEW = "company_overview"
SCHEDULE = "schedule"
SCHEDULE_MEETING = "schedule_meeting"
TASKS = (STAGE_PLANNER, PROPOSAL, ARCHITECTURE, PROJECT_TASKS, COMPANY_OVERVIEW, SCHEDULE, SCHEDULE_MEETING)

#: The engagement stages the project task tracker groups its tasks under (id, name).
PROJECT_STAGES = (
    ("discover", "Discover"),
    ("assess", "Assess current portal"),
    ("design", "Design"),
    ("propose", "Propose"),
    ("build", "Build"),
    ("launch", "Test & launch"),
)
MAX_SUGGESTED_TASKS_PER_STAGE = 8

#: Kinds of client meeting the Schedule Planner plans (id, name).
MEETING_TYPES = (
    ("kickoff", "Kickoff"),
    ("discovery", "Discovery deep-dive"),
    ("requirements", "Requirements review"),
    ("design", "Design review"),
    ("build", "Build check-in"),
    ("data", "Data & migration"),
    ("training", "Training"),
    ("uat", "UAT / testing"),
    ("go_live", "Go-live"),
    ("review", "Retrospective / handover"),
    ("other", "Other"),
)
MAX_SUGGESTED_MEETINGS = 20
_MEETING_LISTS = ("agenda", "prepare", "review", "attendees", "follow_ups")
_MEETING_TEXTS = ("purpose", "explain", "notes")
_MAX_LIST_ITEMS = 10

MAX_TOKENS = 8000
GEMINI_MAX_OUTPUT_TOKENS = 32768

SYSTEM_PROMPT = """You are a senior HubSpot solutions architect at SonaMation, a HubSpot partner. \
You prepare a client engagement from what the team already captured: discovery call notes, \
a business analysis, a requirements document, a joint evaluation plan.

Rules:
- Use only facts in the provided context. Never invent client names, numbers, dates, systems or people. \
When the context is silent, use common HubSpot practice for this kind of business and keep it generic.
- Write in plain, professional business English. No emoji, no marketing hype.
- Fill only the fields the task asks for, and return exactly the JSON shape requested: \
a single JSON object, no markdown fences, no commentary.
- Leave a field as "" (or []) when there is nothing sensible to put in it."""


class AssistError(RuntimeError):
    """The model's answer couldn't be used (refused, cut off, or not JSON)."""


# ---- context ----------------------------------------------------------------


def _clean(value: Any) -> str:
    return str(value or "").strip()


def discovery_context(notes: dict[str, dict[str, Any]], *, client_name: str = "", business_type: str = "") -> dict[str, Any]:
    """The discovery notes as the business-analysis input, minus every blank
    answer and empty section (they carry no facts for a suggestion)."""
    if not dd.has_any_notes(notes):
        return {}
    payload = dd.build_business_analysis_input(notes, client_name=client_name, business_type=business_type)
    sections = {}
    for name, section in payload["sections"].items():
        answers = {q: a for q, a in section["answers"].items() if _clean(a)}
        kept = {k: v for k, v in (("answers", answers), ("notes", section["notes"]), ("edge_cases", section["edge_cases"])) if v}
        if kept:
            sections[name] = kept
    return {"client": payload["client"], "sections": sections}


def _compact_documents(documents: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    """``{document: {section: rows}}`` without empty cells, rows or sections."""
    out: dict[str, Any] = {}
    for doc, sections in (documents or {}).items():
        kept_sections = {}
        for title, rows in (sections or {}).items():
            kept_rows = [{k: v for k, v in row.items() if _clean(v)} for row in rows or []]
            kept_rows = [r for r in kept_rows if r]
            if kept_rows:
                kept_sections[title] = kept_rows
        if kept_sections:
            out[doc] = kept_sections
    return out


def build_context(
    *,
    discovery: dict[str, Any] | None = None,
    business_analysis: str = "",
    documents: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
    stage_planner: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Everything the project holds, ready to send; empty parts left out."""
    context: dict[str, Any] = {}
    if discovery:
        context["discovery_call"] = discovery
    if _clean(business_analysis):
        context["business_analysis"] = business_analysis.strip()
    if docs := _compact_documents(documents or {}):
        context["documents"] = docs
    if stage_planner:
        context["deal_stage_planner"] = stage_planner
    return context


def has_context(context: dict[str, Any]) -> bool:
    return bool(context)


# ---- tasks ----------------------------------------------------------------------

_STAGE_SHAPE = {
    "stages": [
        {
            "name": "Stage name",
            "forecast": "Win probability 0-100 as a number, or null",
            "entry_criteria": "What must be true for a deal to enter this stage",
            "exit_criteria": "What must be true to move on",
            "actions": "What the rep does in this stage",
            "automations": "HubSpot automations to run (tasks, emails, notifications, property updates)",
            "fields": ["Deal properties required at this stage"],
        }
    ]
}

_ARCH_OPTIONS = {
    "standard_objects": ["Contact", "Company", "Deal", "Ticket", "Location", "Child", "Family"],
    "custom_object_keywords": ["Membership", "Subscription", "Location", "Event"],
    "regions": ["United States", "Canada", "United Kingdom", "European Union", "Australia"],
    "currencies": ["USD", "CAD", "GBP", "EUR", "AUD"],
    "integrations": ["MyStudio", "Sakari", "Payments Provider"],
    "hubs_in_scope": ["Marketing Hub", "Sales Hub", "Service Hub", "CMS Hub", "Operations Hub", "Commerce Hub"],
}

_ARCH_SHAPE = {
    "standard_objects": ["..."],
    "custom_object_keywords": ["..."],
    "custom_object_notes": "",
    "pipelines_required": ["Object names that need a pipeline, e.g. Deal, Ticket"],
    "regions": ["..."],
    "currencies": ["..."],
    "integrations": ["..."],
    "other_integration_notes": "",
    "record_volumes": {"Contact": 0},
    "hubs_in_scope": ["..."],
}

_PROPOSAL_SHAPE = {
    "executive_summary": "2-3 plain-language sentences a non-technical approver reads first: what is being done and the outcome",
    "exec_key_risks": "1-2 sentences: the main risks to the project",
    "exec_dependencies": "1-2 sentences: what delivery depends on from the client",
    "problem_statement": "The client's problem and why it matters; lines may start with '- ' for bullets",
    "current_state": "Their systems and process today",
    "solution_overview": "How the requirements will be met in HubSpot; lines may start with '- '",
    "objectives": [{"objective": "", "success_measure": ""}],
    "scope": [
        {
            "status": "In Scope | Out of Scope | Optional Add-on | Client Responsibility",
            "workstream": "",
            "item": "A concrete deliverable",
            "quantity_limit": "e.g. 'Up to 3 pipelines'",
            "acceptance_criteria": "",
            "requirement_ids": "IDs of the proposal requirements it delivers, e.g. 'R-1, R-3'",
        }
    ],
    "assumptions": ["..."],
    "risks": [{"risk": "", "likelihood": "Low | Medium | High", "impact": "Low | Medium | High", "mitigation": ""}],
    "kpis": [{"type": "Primary | Secondary", "kpi": "", "definition": "", "target": ""}],
    "client_responsibilities": ["What the client must do or provide"],
    "vendor_responsibilities": ["What SonaMation commits to"],
    "data_quality": [
        {"issue": "A known data problem from the context", "risk_if_not_resolved": "", "owner": "Client | SonaMation"}
    ],
    "timeline": [{"phase": "", "start_week": 1, "duration_weeks": 2, "key_deliverables": ""}],
}


def proposal_brief(proposal: dict[str, Any]) -> dict[str, Any]:
    """The parts of a proposal (domain form) the model needs — not the
    boilerplate terms, pricing or team — with empty rows dropped."""
    client = proposal.get("client") or {}
    return {
        "document_type": _clean(proposal.get("document_type")),
        "title": _clean(proposal.get("title")),
        "client": _clean(client.get("company")),
        **{key: _clean(proposal.get(key)) for key in _PROPOSAL_TEXTS},
        "requirements": [
            {"id": r.get("ID"), "requirement": _clean(r.get("Requirement")), "priority": _clean(r.get("Priority"))}
            for r in pp.number_requirements(pp.nonblank(proposal.get("requirements", []), "Requirement"))
        ],
        "objectives": [_clean(o.get("Objective")) for o in pp.nonblank(proposal.get("objectives", []), "Objective")],
        "scope": [
            {
                "id": s.get("ID"),
                "status": _clean(s.get("Status")),
                "item": _clean(s.get("Item")),
                "requirement_ids": _clean(s.get("Req. ID")),
            }
            for s in pp.number_scope_items(pp.nonblank(proposal.get("scope", []), "Item"))
        ],
        "assumptions": [_clean(a.get("Assumption")) for a in pp.nonblank(proposal.get("assumptions", []), "Assumption")],
        "risks": [_clean(r.get("Risk")) for r in pp.nonblank(proposal.get("risks", []), "Risk")],
        "kpis": [_clean(k.get("KPI")) for k in pp.nonblank(proposal.get("kpis", []), "KPI")],
    }


def instructions(task: str, current: Any) -> str:
    """The task-specific part of the request: what to fill and the exact JSON shape."""
    if task == STAGE_PLANNER:
        return (
            "Task: design the client's HubSpot deal pipeline for the Deal Stage Planner.\n"
            "If CURRENT_STAGES is empty, propose the full ordered list of stages (usually 5-8, ending with "
            "Closed Won and Closed Lost) that matches how this client sells. Otherwise keep exactly those stage "
            "names in that order and fill in their details.\n"
            "Closed Won has forecast 100 and Closed Lost 0.\n"
            f"CURRENT_STAGES: {json.dumps(current, ensure_ascii=False)}\n"
            f"Return JSON shaped like: {json.dumps(_STAGE_SHAPE, ensure_ascii=False)}"
        )
    if task == ARCHITECTURE:
        return (
            "Task: fill in the Architecture Generator's project inputs for this client's HubSpot portal.\n"
            f"Use these known values where they fit: {json.dumps(_ARCH_OPTIONS, ensure_ascii=False)}.\n"
            "Every company also needs things the lists don't have, and proposing them is the most useful part "
            "of this task:\n"
            "- custom_object_keywords: propose a custom object for each business entity the context describes "
            "that HubSpot's standard objects can't hold — named in the discovery answers ('Custom data "
            "elements'), the requirements, CURRENT_INPUTS.custom_object_notes, or the stage planner (e.g. "
            "'Division', 'Vendor', 'Asset', 'Contract', 'Clearance'). Use a short singular business name, not "
            "a sentence.\n"
            "- pipelines_required: add a custom object's name when it moves through stages (approvals, "
            "renewals, onboarding).\n"
            "- integrations: name each system the client must connect (e.g. 'NetSuite', 'Microsoft Dynamics "
            "365', 'Dentrix'), never a generic 'Other'.\n"
            "- regions / currencies: as stated; currencies are ISO codes.\n"
            "record_volumes maps object names to estimated record counts; include only counts the context states.\n"
            f"CURRENT_INPUTS: {json.dumps(current, ensure_ascii=False)}\n"
            f"Return JSON shaped like: {json.dumps(_ARCH_SHAPE, ensure_ascii=False)}"
        )
    if task == PROPOSAL:
        return (
            "Task: give the seller a starting point for the proposal / Statement of Work.\n"
            "Write the narrative fields from the context, and propose objectives, scope items, assumptions, "
            "risks and KPIs. Scope items must be concrete deliverables with a quantity limit and acceptance "
            "criteria; cite the requirement IDs from CURRENT_PROPOSAL.requirements that each one delivers, and "
            "list common requests that are not included as Out of Scope.\n"
            "Also propose each party's responsibilities, an indicative timeline in weeks (phases may overlap: "
            "start_week is the week a phase begins, from 1), and data_quality rows only for data problems the "
            "context actually mentions (portal audit findings, duplicates, missing fields, messy source data).\n"
            f"CURRENT_PROPOSAL: {json.dumps(current, ensure_ascii=False)}\n"
            f"Return JSON shaped like: {json.dumps(_PROPOSAL_SHAPE, ensure_ascii=False)}"
        )
    if task == PROJECT_TASKS:
        return (
            "Task: plan the follow-up work for this HubSpot engagement as a checklist, grouped by stage.\n"
            f"Stages (id: name): {json.dumps(dict(PROJECT_STAGES), ensure_ascii=False)}.\n"
            "For each stage propose the concrete tasks this particular client needs (at most "
            f"{MAX_SUGGESTED_TASKS_PER_STAGE} per stage, fewer when the context is thin), such as confirming "
            "an open question, collecting access, configuring a named object, migrating a named system, or "
            "testing a named workflow. Each task is a short imperative title, plus a one-sentence source: "
            "why it is needed, citing where in the context it comes from.\n"
            "Do not repeat a task already in CURRENT_TASKS (same meaning counts as a repeat).\n"
            f"CURRENT_TASKS: {json.dumps(current, ensure_ascii=False)}\n"
            'Return JSON shaped like: {"tasks": [{"stage": "discover", "title": "", "source": ""}]}'
        )
    if task == SCHEDULE:
        return (
            "Task: plan the series of client meetings for this HubSpot engagement for the Schedule Planner.\n"
            "Follow SETTINGS: the start date, cadence, target go-live date, meeting length and any scheduling "
            "notes; if SETTINGS.meeting_count is set, propose about that many meetings. Order them as they "
            "should happen, from kickoff to go-live and handover, and tie each one to this client: name the "
            "processes, objects, systems and open questions from the context that it covers.\n"
            f"type is one of {json.dumps([t for t, _ in MEETING_TYPES])}; "
            f"stage is one of {json.dumps([s for s, _ in PROJECT_STAGES])}.\n"
            "week is the 1-based week from the start date the meeting belongs in (spread them to reach go-live "
            "on time). agenda holds 3-6 short items; prepare lists what the team and the client must have ready "
            "before it; review lists what is reviewed or decided in it; explain says what to walk the client "
            "through and why it matters; attendees are roles (e.g. 'Client sales lead'), never invented names.\n"
            "Do not repeat a meeting already in CURRENT_PLAN.meetings (same purpose counts as a repeat).\n"
            f"CURRENT_PLAN: {json.dumps(current, ensure_ascii=False)}\n"
            "Return JSON shaped like: "
            + json.dumps(
                {
                    "meetings": [
                        {
                            "title": "Kickoff & goals",
                            "type": "kickoff",
                            "stage": "discover",
                            "week": 1,
                            "duration_minutes": 60,
                            "purpose": "One or two sentences",
                            "agenda": [""],
                            "prepare": [""],
                            "review": [""],
                            "explain": "",
                            "attendees": [""],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
    if task == SCHEDULE_MEETING:
        return (
            "Task: prepare one client meeting from the Schedule Planner (CURRENT_MEETING), in the context of the "
            "whole plan (CURRENT_MEETING.other_meetings) and the project.\n"
            "Propose its purpose, a timed agenda (3-6 items), what to prepare beforehand, what to review or "
            "decide, what to explain to the client, attendee roles, follow-ups to send afterwards, and short "
            "facilitator notes (risks, open questions from discovery to raise). Be specific to this client; "
            "don't repeat what CURRENT_MEETING already lists.\n"
            f"CURRENT_MEETING: {json.dumps(current, ensure_ascii=False)}\n"
            "Return JSON shaped like: "
            + json.dumps(
                {
                    "purpose": "",
                    "agenda": ["10 min - ..."],
                    "prepare": [""],
                    "review": [""],
                    "explain": "",
                    "attendees": [""],
                    "follow_ups": [""],
                    "notes": "",
                },
                ensure_ascii=False,
            )
        )
    if task == COMPANY_OVERVIEW:
        return (
            "Task: write a short company overview of the client for the consultant preparing the discovery "
            "call, from the website excerpt (and any other context). Facts only from the context; leave a field "
            "empty rather than guess. Lists hold short phrases.\n"
            "Return JSON shaped like: "
            + json.dumps(
                {
                    "name": "Company name",
                    "type": "Industry / type of business, e.g. 'Multi-location dental group'",
                    "summary": "2-3 sentences: what they do, for whom, where",
                    "offerings": ["Main products or services"],
                    "audience": "Who their customers are",
                    "locations": "Where they operate, if stated",
                    "highlights": ["Notable facts: size, awards, growth, differentiators"],
                    "things_to_know": [
                        "What matters for a HubSpot engagement: channels they use, booking or "
                        "checkout flows, tools seen on the site, compliance hints"
                    ],
                    "questions_to_ask": ["Good discovery questions this overview raises"],
                },
                ensure_ascii=False,
            )
        )
    raise ValueError(f"Unknown assist task: {task}")


def user_message(task: str, context: dict[str, Any], current: Any) -> str:
    return "CONTEXT:\n" + json.dumps(context, ensure_ascii=False, indent=1) + "\n\n" + instructions(task, current)


# ---- calling the model ----------------------------------------------------------


def parse_json(text: str) -> dict[str, Any]:
    """The JSON object in a model answer (tolerates code fences or a stray sentence around it)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise AssistError("The model didn't return any suggestions. Try again.")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AssistError("The model's suggestions couldn't be read. Try again.") from exc
    if not isinstance(value, dict):
        raise AssistError("The model's suggestions couldn't be read. Try again.")
    return value


def ask_claude(client: Any, task: str, context: dict[str, Any], current: Any, *, model: str | None = None) -> dict[str, Any]:
    response = client.messages.create(
        model=model or dd.model_id(),
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message(task, context, current)}],
    )
    if response.stop_reason == "refusal":
        raise AssistError("The model declined to make suggestions for this project.")
    if response.stop_reason == "max_tokens":
        raise AssistError("The suggestions were cut off. Try again.")
    text = "".join(getattr(block, "text", "") for block in response.content if getattr(block, "type", "") == "text")
    return parse_json(text)


def ask_gemini(
    client: Any,
    task: str,
    context: dict[str, Any],
    current: Any,
    *,
    models: Sequence[str],
    classify: Callable[[Exception], str | None],
) -> tuple[dict[str, Any], str]:
    """Try ``models`` in order; a busy or unavailable model (``classify``
    returns a value) moves on to the next. Returns the answer and the model."""
    last: Exception | None = None
    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_message(task, context, current),
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
                },
            )
        except Exception as exc:
            if classify(exc) is None:
                raise
            last = exc
            continue
        text = getattr(response, "text", None) or ""
        if not text.strip():
            raise AssistError("The model returned no suggestions (it may have been blocked). Try again.")
        return parse_json(text), model
    assert last is not None
    raise last


# ---- merging: fill blanks only ------------------------------------------------


def _number_or_none(value: Any) -> float | None:
    try:
        n = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, n))


def _fields(value: Any) -> list[str]:
    items = value if isinstance(value, list) else str(value or "").split(",")
    return [s for s in (_clean(v) for v in items) if s]


def merge_stages(current: list[dict[str, Any]], suggested: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Stage-planner rows with blanks filled from ``suggested``. With no
    current stages the suggested pipeline is taken whole; otherwise stages
    are matched by name and only their empty cells are filled (no stage is
    added or removed). Returns the rows and how many cells were filled."""
    proposed = [s for s in suggested.get("stages", []) if isinstance(s, dict) and _clean(s.get("name"))]
    if not any(_clean(s.get("name")) for s in current):
        rows = [
            {
                "name": _clean(s.get("name")),
                "forecast": _number_or_none(s.get("forecast")),
                "entry_criteria": _clean(s.get("entry_criteria")),
                "exit_criteria": _clean(s.get("exit_criteria")),
                "actions": _clean(s.get("actions")),
                "automations": _clean(s.get("automations")),
                "fields": _fields(s.get("fields")),
            }
            for s in proposed
        ]
        filled = sum(bool(v) or v == 0 for r in rows for k, v in r.items() if k != "name" and v is not None)
        return rows, filled
    by_name = {_clean(s.get("name")).lower(): s for s in proposed}
    rows, filled = [], 0
    for stage in current:
        row = dict(stage)
        match = by_name.get(_clean(stage.get("name")).lower())
        if match:
            if row.get("forecast") is None and (forecast := _number_or_none(match.get("forecast"))) is not None:
                row["forecast"], filled = forecast, filled + 1
            for key in ("entry_criteria", "exit_criteria", "actions", "automations"):
                if not _clean(row.get(key)) and _clean(match.get(key)):
                    row[key], filled = _clean(match.get(key)), filled + 1
            if not row.get("fields") and (fields := _fields(match.get("fields"))):
                row["fields"], filled = fields, filled + 1
        rows.append(row)
    return rows, filled


_ARCH_LISTS = (
    "standard_objects",
    "custom_object_keywords",
    "pipelines_required",
    "regions",
    "currencies",
    "integrations",
    "hubs_in_scope",
)
_ARCH_TEXTS = ("custom_object_notes", "other_integration_notes")


def merge_architecture(current: dict[str, Any], suggested: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Architecture inputs with suggestions added: list values are added to
    what's selected (nothing removed), text and volumes fill only blanks."""
    merged = dict(current)
    added = 0
    for key in _ARCH_LISTS:
        have = list(current.get(key) or [])
        seen = {v.lower() for v in have}
        for value in _fields(suggested.get(key)):
            if value.lower() not in seen:
                have.append(value)
                seen.add(value.lower())
                added += 1
        merged[key] = have
    for key in _ARCH_TEXTS:
        if not _clean(current.get(key)) and _clean(suggested.get(key)):
            merged[key] = _clean(suggested.get(key))
            added += 1
    volumes = dict(current.get("record_volumes") or {})
    for obj, count in (suggested.get("record_volumes") or {}).items():
        try:
            n = int(float(count))
        except (TypeError, ValueError):
            continue
        if _clean(obj) and n > 0 and obj not in volumes:
            volumes[_clean(obj)] = n
            added += 1
    merged["record_volumes"] = volumes
    return merged, added


_PROPOSAL_TEXTS = (
    "executive_summary",
    "exec_key_risks",
    "exec_dependencies",
    "problem_statement",
    "current_state",
    "solution_overview",
)
_LEVELS = {"low": "Low", "medium": "Medium", "high": "High"}


def _choice(value: Any, allowed: Sequence[str], default: str) -> str:
    text = _clean(value).lower()
    return next((a for a in allowed if a.lower() == text), default)


def merge_proposal(proposal: dict[str, Any], suggested: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """``proposal`` (domain form) with blank narrative fields written and
    suggested rows appended where the proposal doesn't already have them.
    Returns the proposal and the names of the parts that changed."""
    p = dict(proposal)
    changed: list[str] = []
    for key in _PROPOSAL_TEXTS:
        if not _clean(p.get(key)) and _clean(suggested.get(key)):
            p[key] = _clean(suggested[key])
            changed.append(key)

    def rows(key: str, build: Callable[[dict[str, Any]], dict[str, Any] | None]) -> list[dict[str, Any]]:
        out = []
        for item in suggested.get(key) or []:
            row = build(item if isinstance(item, dict) else {"value": item})
            if row:
                out.append(row)
        return out

    tables: dict[str, tuple[list[dict[str, Any]], tuple[str, ...]]] = {
        "objectives": (
            rows(
                "objectives",
                lambda o: (
                    {"Objective": _clean(o.get("objective")), "Success Measure": _clean(o.get("success_measure"))}
                    if _clean(o.get("objective"))
                    else None
                ),
            ),
            ("Objective",),
        ),
        "assumptions": (
            rows(
                "assumptions",
                lambda a: (
                    {"Assumption": _clean(a.get("value") or a.get("assumption"))}
                    if _clean(a.get("value") or a.get("assumption"))
                    else None
                ),
            ),
            ("Assumption",),
        ),
        "risks": (
            rows(
                "risks",
                lambda r: (
                    {
                        **pp.BLANK_ROWS["risks"],
                        "Risk": _clean(r.get("risk")),
                        "Likelihood": _LEVELS.get(_clean(r.get("likelihood")).lower(), "Medium"),
                        "Impact": _LEVELS.get(_clean(r.get("impact")).lower(), "Medium"),
                        "Mitigation": _clean(r.get("mitigation")),
                    }
                    if _clean(r.get("risk"))
                    else None
                ),
            ),
            ("Risk",),
        ),
        "kpis": (
            rows(
                "kpis",
                lambda k: (
                    {
                        **pp.BLANK_ROWS["kpis"],
                        "Type": _choice(k.get("type"), ("Primary", "Secondary"), "Primary"),
                        "KPI": _clean(k.get("kpi")),
                        "Definition": _clean(k.get("definition")),
                        "Target": _clean(k.get("target")),
                    }
                    if _clean(k.get("kpi"))
                    else None
                ),
            ),
            ("KPI",),
        ),
        "scope": (
            rows(
                "scope",
                lambda s: (
                    {
                        **pp.BLANK_ROWS["scope"],
                        "Status": _choice(s.get("status"), pp.SCOPE_STATUSES, pp.SCOPE_IN),
                        "Workstream": _clean(s.get("workstream")),
                        "Item": _clean(s.get("item")),
                        "Quantity / Limit": _clean(s.get("quantity_limit")),
                        "Acceptance Criteria": _clean(s.get("acceptance_criteria")),
                        "Req. ID": _clean(s.get("requirement_ids")),
                    }
                    if _clean(s.get("item"))
                    else None
                ),
            ),
            ("Item",),
        ),
        "client_responsibilities": (
            rows(
                "client_responsibilities",
                lambda r: {"Responsibility": _clean(r.get("value"))} if _clean(r.get("value")) else None,
            ),
            ("Responsibility",),
        ),
        "vendor_responsibilities": (
            rows(
                "vendor_responsibilities",
                lambda r: {"Responsibility": _clean(r.get("value"))} if _clean(r.get("value")) else None,
            ),
            ("Responsibility",),
        ),
        "data_quality": (
            rows(
                "data_quality",
                lambda d: (
                    {
                        "Issue": _clean(d.get("issue")),
                        "Risk if Not Resolved": _clean(d.get("risk_if_not_resolved")),
                        "Owner": _choice(d.get("owner"), pp.DATA_QUALITY_OWNERS, "Client"),
                    }
                    if _clean(d.get("issue"))
                    else None
                ),
            ),
            ("Issue",),
        ),
        "timeline": (
            rows(
                "timeline",
                lambda t: (
                    {
                        **pp.BLANK_ROWS["timeline"],
                        "Phase / Milestone": _clean(t.get("phase")),
                        "Start Week": max(0.0, pp.to_float(t.get("start_week"))),
                        "Duration (Weeks)": max(0.0, pp.to_float(t.get("duration_weeks"))),
                        "Key Deliverables": _clean(t.get("key_deliverables")),
                    }
                    if _clean(t.get("phase"))
                    else None
                ),
            ),
            ("Phase / Milestone",),
        ),
    }
    for key, (new_rows, columns) in tables.items():
        if not new_rows:
            continue
        before = pp.nonblank(p.get(key, []), *columns)
        merged = pp.merge_rows(p.get(key, []), new_rows, *columns)
        if key == "scope":
            merged = pp.number_scope_items(merged)
        if len(merged) != len(before):
            p[key] = merged
            changed.append(key)
    return p, changed


# ---- Project tasks / company overview ----------------------------------------------


def merge_tasks(current: list[dict[str, Any]], suggested: dict[str, Any]) -> list[dict[str, str]]:
    """The suggested tasks that are new: on a known stage, with a title, not
    already a task (by meaning-insensitive text) and capped per stage."""
    stage_ids = {sid for sid, _ in PROJECT_STAGES}
    seen = {task_key(t.get("title")) for t in current}
    per_stage: dict[str, int] = {}
    new = []
    for item in suggested.get("tasks") or []:
        if not isinstance(item, dict):
            continue
        stage, title = _clean(item.get("stage")), _clean(item.get("title"))
        if stage not in stage_ids or not title or task_key(title) in seen:
            continue
        if per_stage.get(stage, 0) >= MAX_SUGGESTED_TASKS_PER_STAGE:
            continue
        per_stage[stage] = per_stage.get(stage, 0) + 1
        seen.add(task_key(title))
        new.append({"stage": stage, "title": title, "source": _clean(item.get("source"))})
    return new


def task_key(value: Any) -> str:
    """Comparable form of a task title (case, spacing and punctuation ignored)."""
    return " ".join(re.sub(r"[^\w\s]", " ", _clean(value).lower()).split())


_OVERVIEW_TEXT = ("name", "type", "summary", "audience", "locations")
_OVERVIEW_LISTS = ("offerings", "highlights", "things_to_know", "questions_to_ask")


def clean_overview(suggested: dict[str, Any]) -> dict[str, Any]:
    """The model's overview with every expected field present and tidy."""
    out: dict[str, Any] = {key: _clean(suggested.get(key)) for key in _OVERVIEW_TEXT}
    for key in _OVERVIEW_LISTS:
        items = suggested.get(key)
        out[key] = [s for s in (_clean(v) for v in (items if isinstance(items, list) else [])) if s][:8]
    return out


# ---- Schedule Planner --------------------------------------------------------------


def _text_list(value: Any, limit: int = _MAX_LIST_ITEMS) -> list[str]:
    """Non-empty strings from a list, de-duplicated by meaning, at most ``limit``."""
    out: list[str] = []
    seen: set[str] = set()
    for item in value if isinstance(value, list) else []:
        text = _clean(item)
        if text and task_key(text) not in seen:
            seen.add(task_key(text))
            out.append(text)
    return out[:limit]


def _bounded_int(value: Any, low: int, high: int) -> int | None:
    try:
        n = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return n if low <= n <= high else None


def merge_meetings(current: list[dict[str, Any]], suggested: dict[str, Any]) -> list[dict[str, Any]]:
    """The suggested meetings that are new (by title), tidied: a known type
    and stage (else "other" / ""), a week and length in range (else None),
    and short de-duplicated lists. At most :data:`MAX_SUGGESTED_MEETINGS`."""
    types = {t for t, _ in MEETING_TYPES}
    stages = {s for s, _ in PROJECT_STAGES}
    seen = {task_key(m.get("title")) for m in current}
    new: list[dict[str, Any]] = []
    for item in suggested.get("meetings") or []:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("title"))
        if not title or task_key(title) in seen:
            continue
        seen.add(task_key(title))
        kind, stage = _clean(item.get("type")).lower(), _clean(item.get("stage")).lower()
        new.append(
            {
                "title": title,
                "type": kind if kind in types else "other",
                "stage": stage if stage in stages else "",
                "week": _bounded_int(item.get("week"), 1, 104),
                "duration_minutes": _bounded_int(item.get("duration_minutes"), 15, 480),
                "purpose": _clean(item.get("purpose")),
                "agenda": _text_list(item.get("agenda")),
                "prepare": _text_list(item.get("prepare")),
                "review": _text_list(item.get("review")),
                "explain": _clean(item.get("explain")),
                "attendees": _text_list(item.get("attendees")),
            }
        )
        if len(new) >= MAX_SUGGESTED_MEETINGS:
            break
    return new


def merge_meeting_content(current: dict[str, Any], suggested: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """One meeting's content with blanks filled from ``suggested``: empty
    texts are filled and lists get the new items appended, so typed text is
    never replaced. Returns the content and the fields that changed."""
    out: dict[str, Any] = {}
    changed: list[str] = []
    for key in _MEETING_TEXTS:
        mine, theirs = _clean(current.get(key)), _clean(suggested.get(key))
        out[key] = mine or theirs
        if not mine and theirs:
            changed.append(key)
    for key in _MEETING_LISTS:
        mine_list = _text_list(current.get(key), limit=50)
        seen = {task_key(v) for v in mine_list}
        extra = [v for v in _text_list(suggested.get(key)) if task_key(v) not in seen]
        out[key] = mine_list + extra
        if extra:
            changed.append(key)
    return out, changed
