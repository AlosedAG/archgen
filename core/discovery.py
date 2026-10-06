"""Discovery Call Assistant — question bank, request building, and the
Claude call that turns raw live-call notes into finished documents.

Two modes, matching the system prompt below:

- ``business_analysis`` — the specialist's notes (Goals, Data, Processes,
  Solutions Design) become a structured discovery / business-analysis
  document, with every blank field surfaced as a follow-up gap rather than
  guessed at.
- ``client_explainer`` — a plain-language explainer of selected HubSpot
  hubs for a non-technical client.

The questions themselves (labels, input types, dropdown options) live in
``config/discovery_options.yaml``, loaded by :mod:`core.discovery_config`.

Kept free of Streamlit so it's unit-testable with a fake Anthropic client:
the page (``app_pages/11_Discovery_Call_Assistant.py``) only collects
inputs and renders what :func:`stream_document` yields.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Iterator

from core.discovery_config import Question, QuestionBank, load_question_bank

DEFAULT_MODEL = "claude-opus-5-5"
# Server-side refusal fallback: if a safety classifier declines the request,
# the API re-runs it on Anthropic's recommended fallback model in the same
# call instead of returning an empty document.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 32000

MODE_BUSINESS_ANALYSIS = "business_analysis"
MODE_CLIENT_EXPLAINER = "client_explainer"


def model_id() -> str:
    """``ANTHROPIC_MODEL`` env override, else the default model."""
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def question_bank() -> QuestionBank:
    """The discovery question bank from ``config/discovery_options.yaml``
    (re-read when the file changes). Raises
    :class:`~core.discovery_config.DiscoveryConfigError` if it's invalid."""
    return load_question_bank()


def sections() -> dict[str, list[Question]]:
    """Section name -> discovery questions, in the order they're usually
    asked. Labels are what the model sees as the question each answer
    belongs to."""
    return question_bank().sections


HUBSPOT_MODULES: list[str] = [
    "Marketing Hub",
    "Sales Hub",
    "Service Hub",
    "Operations Hub",
    "Content Hub (CMS)",
    "Commerce Hub",
]

# Alternate names the business-analysis output might use for a module,
# so :func:`suggest_modules` can map them back to HUBSPOT_MODULES.
_MODULE_ALIASES: dict[str, list[str]] = {
    "Marketing Hub": ["marketing hub", "marketing"],
    "Sales Hub": ["sales hub", "sales"],
    "Service Hub": ["service hub", "service"],
    "Operations Hub": ["operations hub", "data hub", "operations", "ops hub"],
    "Content Hub (CMS)": ["content hub", "cms hub", "cms"],
    "Commerce Hub": ["commerce hub", "commerce"],
}


# The system prompt, verbatim from the module spec. Kept byte-stable (no
# timestamps or per-request data) so it can be prompt-cached across calls.
SYSTEM_PROMPT = """Discovery Call Assistant (ArchitectureScope · Discovery Module)

ROLE
You are a HubSpot Solutions Architecture assistant embedded in a discovery-call tool. An implementation specialist fills your input fields live, during a client call — so the notes you receive will be fragmentary, shorthand, out of order, and sometimes incomplete. Your job is to turn those raw notes into clean, professional, structured output. You never invent facts the specialist did not capture; where information is missing, you flag it as a gap to follow up on rather than guessing.

TWO MODES
You operate in one of two modes, specified by the mode field in the input:

mode: "business_analysis" → Produce a structured discovery / business-analysis document from the specialist's notes.
mode: "client_explainer" → Produce a plain-language explainer of selected HubSpot modules for a non-technical client.
MODE 1 — business_analysis

INPUT
You receive notes grouped under four sections (Goals, Data, Processes, Solutions Design). Each section contains the specialist's answers to discovery questions, plus a free-form notes field and any flagged edge_cases. Fields may be blank.

OUTPUT — produce a document with these sections, in this order:

Executive Summary (3–5 sentences)
The client's business in one line, their core goal for this engagement, their current situation, and what they want HubSpot to achieve. Written so a colleague who wasn't on the call understands the engagement immediately.
Goals & Success Criteria
Summarize the client's growth areas, long-term goals, and the KPIs they'll measure success by.
List each stated goal with its associated success metric where captured.
Note their timeline and their reason for switching to HubSpot (this is critical context — restate it clearly).
Flag: any goal stated without a measurable success criterion.
Current State — Data
Where data lives today, what systems manage it, volume (objects/records/assets), and sync direction(s) needed.
Identify any custom data elements that imply custom objects or properties in HubSpot.
Note data owners/roles, update/cleansing frequency, and any security/compliance requirements (treat these as high-priority — call them out distinctly).
Flag: unknown data volumes, undefined sync direction, or unclear source-of-truth.
Current State — Processes
Summarize the customer journey stages, current team processes, communication methods, SLAs, existing automations, and current reporting.
Identify pain points explicitly (challenges/workarounds mentioned).
Flag: processes the client couldn't clearly describe (a key risk signal).
Solutions Design — Requirements
Primary users, team sizes, required actions/workflows, prior-tool experience, needed integrations, priority features, feature gaps in current tool, and desired MVP date.
Translate stated needs into preliminary HubSpot requirements (e.g., "needs two-way contact sync with ERP" → "requires Operations Hub / Data Sync").
Flag: integrations or features whose feasibility needs technical validation.
Preliminary Scope Signals (bridge to SOW)
Based only on what was captured, list what appears in scope, what the client is likely to assume is included but wasn't discussed (flag for explicit exclusion), and what looks like a potential add-on.
Do NOT produce a final SOW — produce the inputs a SOW builder needs.
Open Questions & Gaps
A bulleted list of everything the specialist did NOT capture that is needed before scoping. This is the follow-up checklist. Be specific ("Did not confirm data volume for the Deals object" not "need more data info").
Recommended HubSpot Modules (if the client's needs map to specific hubs)
List the HubSpot hubs/modules the needs point to (Marketing, Sales, Service, Operations, CMS, Commerce) with a one-line reason each. This feeds the client_explainer mode.

RULES

Never fabricate. If a field is empty, the information goes in "Open Questions & Gaps," not into the body as an assumption.
Preserve the client's own terminology (capture it; if they call members "patients," use "patients").
Highlight compliance, data-security, and multi-location/multi-entity signals prominently — these are the edge cases that cause downstream failures if missed.
Keep it professional and client-ready in tone, but factual — this is a working document, not a sales pitch.
Where the notes contradict themselves, surface the contradiction rather than resolving it silently.
MODE 2 — client_explainer

INPUT
A list of selected HubSpot modules (e.g., ["Marketing Hub", "Sales Hub"]) and optionally the client's business type.

OUTPUT
For each selected module, produce an extremely simple, non-technical explainer aimed at a client who has never used HubSpot. The client must be able to read it during or right after the call and understand what the module does and decide if they want it.

For each module, produce:

A one-sentence plain-language summary of what it's for ("Marketing Hub helps you attract people and turn them into leads through email, ads, and your website.")
4–7 bullet points, each one short, concrete, and jargon-free, describing capabilities in everyday language. Example style:
"Send customizable emails — add your logo, images, and buttons that link to your website."
"Build landing pages and forms to collect new leads, no coding needed."
"See which emails and pages are working with simple reports."
A one-line "What this is good for" tying it to common business outcomes.

RULES

Target a reading level a busy non-technical business owner can skim in under a minute per module.
No HubSpot jargon, no acronyms without plain explanation. Never say "workflows" without saying "automated steps."
Concrete over abstract: "schedule social posts ahead of time" beats "social media management capabilities."
Keep each module to roughly half a page.
If the client's business type is provided, add ONE tailored bullet ("For a dental practice, you could automatically remind patients about appointments.").
Do not oversell or promise specific results — describe capabilities, not guarantees.

OUTPUT FORMAT (both modes)
Return clean, structured content ready to render as a document and export to PDF. Use clear section headings. Do not include this prompt, meta-commentary, or explanations of your process — only the finished document content."""

# Appended to every request (not the system prompt, which stays verbatim):
# the app's exporters handle headings, bullets, and bold, not tables.
_FORMAT_NOTE = (
    "Format the document as Markdown: '#' for the document title, '##' for section headings, "
    "'###' for sub-headings, '-' for bullets, and **bold** for emphasis or flags. Do not use tables."
)


class DiscoveryError(RuntimeError):
    """The model couldn't produce a complete document (refusal or cut off)."""


# Prepended to a section's edge_cases when the specialist ticked "Flag for
# follow-up" on any of its questions. Sent in edge_cases rather than as a
# new payload field so the verbatim system prompt still describes the
# input exactly — it already tells the model to surface edge cases.
FOLLOW_UP_PREFIX = "Specialist flagged for follow-up (confirm before scoping): "


def empty_answer() -> dict[str, Any]:
    """One question's structured answer: the options picked, the "Other
    (specify)" text, shorthand notes, and the follow-up flag. Text-only
    questions keep their answer in ``notes``."""
    return {"selected": [], "other": "", "notes": "", "flagged": False}


def as_answer(value: Any) -> dict[str, Any]:
    """Normalize a stored answer to :func:`empty_answer`'s shape. A plain
    string (notes from before answers were structured) becomes the notes."""
    if isinstance(value, dict):
        answer = {**empty_answer(), **value}
        selected = answer["selected"]
        answer["selected"] = [selected] if isinstance(selected, str) else list(selected or [])
        return answer
    return {**empty_answer(), "notes": str(value or "")}


def format_answer(value: Any, *, other_option: str | None = None) -> str:
    """One answer as the readable line the model receives, e.g.
    ``"HIPAA; Other: state privacy law — notes: legal reviewing"``.
    Empty string when nothing was captured (a gap)."""
    answer = as_answer(value)
    other_option = other_option or question_bank().other_option
    parts = []
    for choice in answer["selected"]:
        if choice == other_option:
            other = str(answer["other"] or "").strip()
            parts.append(f"Other: {other}" if other else "Other (not specified)")
        else:
            parts.append(str(choice))
    text = "; ".join(parts)
    notes = str(answer["notes"] or "").strip()
    if notes:
        text = f"{text} — notes: {notes}" if text else notes
    return text


def empty_notes() -> dict[str, dict[str, Any]]:
    """Blank notes in the shape :func:`build_business_analysis_input` takes."""
    return {
        section: {"answers": {q.key: empty_answer() for q in questions}, "notes": "", "edge_cases": ""}
        for section, questions in sections().items()
    }


def answered_count(section_notes: dict[str, Any]) -> int:
    return sum(1 for v in section_notes.get("answers", {}).values() if format_answer(v))


def flagged_keys(section_notes: dict[str, Any]) -> list[str]:
    """Ids of the questions in a section flagged for follow-up."""
    return [key for key, v in section_notes.get("answers", {}).items() if as_answer(v)["flagged"]]


def has_any_notes(notes: dict[str, dict[str, Any]]) -> bool:
    for section_notes in notes.values():
        if answered_count(section_notes):
            return True
        if str(section_notes.get("notes", "")).strip() or str(section_notes.get("edge_cases", "")).strip():
            return True
    return False


def build_business_analysis_input(
    notes: dict[str, dict[str, Any]], *, client_name: str = "", business_type: str = ""
) -> dict[str, Any]:
    """Request payload for ``business_analysis`` mode. Every question is
    included even when blank — a blank answer is itself information (it
    becomes an Open Questions & Gaps item), so it's sent as ``""`` rather
    than dropped.

    Structured answers are flattened to one line each (see
    :func:`format_answer`), and questions flagged for follow-up are listed
    in the section's ``edge_cases``, so the payload keeps the shape the
    system prompt describes."""
    bank = question_bank()
    payload_sections: dict[str, Any] = {}
    for section, questions in bank.sections.items():
        section_notes = notes.get(section, {})
        answers = section_notes.get("answers", {})
        edge_cases = str(section_notes.get("edge_cases", "") or "").strip()
        flagged = [q.label for q in questions if as_answer(answers.get(q.key))["flagged"]]
        if flagged:
            edge_cases = "\n".join(filter(None, [edge_cases, FOLLOW_UP_PREFIX + "; ".join(flagged)]))
        payload_sections[section] = {
            "answers": {q.label: format_answer(answers.get(q.key), other_option=bank.other_option) for q in questions},
            "notes": str(section_notes.get("notes", "") or "").strip(),
            "edge_cases": edge_cases,
        }
    return {
        "mode": MODE_BUSINESS_ANALYSIS,
        "client": {"name": client_name.strip(), "business_type": business_type.strip()},
        "sections": payload_sections,
    }


def build_client_explainer_input(modules: list[str], *, business_type: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"mode": MODE_CLIENT_EXPLAINER, "modules": list(modules)}
    if business_type.strip():
        payload["business_type"] = business_type.strip()
    return payload


def build_request(payload: dict[str, Any], *, model: str | None = None) -> dict[str, Any]:
    """Keyword arguments for ``client.beta.messages.stream``."""
    return {
        "model": model or model_id(),
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "messages": [
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2) + "\n\n" + _FORMAT_NOTE,
            }
        ],
        # Live-call tool: medium keeps turnaround short while still reasoning
        # through gaps and contradictions in fragmentary notes.
        "output_config": {"effort": "medium"},
        "betas": [FALLBACK_BETA],
        "extra_body": {"fallbacks": "default"},
    }


def stream_document(client: Any, payload: dict[str, Any], *, model: str | None = None) -> Iterator[str]:
    """Yield the document's text as it streams in. Raises
    :class:`DiscoveryError` at the end if the response was refused or cut
    off, so the page never presents a partial document as finished."""
    with client.beta.messages.stream(**build_request(payload, model=model)) as stream:
        yield from stream.text_stream
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        raise DiscoveryError("The model declined to produce this document. Review the notes and try again.")
    if final.stop_reason == "max_tokens":
        raise DiscoveryError("The document was cut off before it finished. Try generating again.")


def suggest_modules(business_analysis_md: str) -> list[str]:
    """HubSpot modules named in the business-analysis document's
    "Recommended HubSpot Modules" section, mapped to :data:`HUBSPOT_MODULES`
    — used to pre-select the client explainer's modules. Empty when the
    section is missing."""
    match = re.search(r"^#+\s*Recommended HubSpot Modules[^\n]*\n(.*?)(?=^#{1,2}\s|\Z)", business_analysis_md, re.M | re.S | re.I)
    if not match:
        return []
    section = match.group(1).lower()
    found = []
    for module in HUBSPOT_MODULES:
        # Match on each bullet's lead (before the reason), so "Sales Hub —
        # ... marketing handoff" doesn't also select Marketing Hub.
        leads = [re.split(r"[—:–]| - ", line.lstrip("-*• ").strip(), maxsplit=1)[0] for line in section.splitlines()]
        if any(re.search(rf"\b{re.escape(alias)}\b", lead) for lead in leads for alias in _MODULE_ALIASES[module]):
            found.append(module)
    return found
