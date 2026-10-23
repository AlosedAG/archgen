"""The SOW's terms: an editable library of boilerplate clauses.

Each workspace keeps its own standard set (seeded from :data:`DEFAULT_CLAUSES`
and edited by its admins), and every SOW holds a copy whose clauses can be
switched on or off and edited for that deal. The texts are **placeholder
templates for the firm's own counsel to review and adapt** — they are not
legal advice. Blanks the seller fills per SOW are written ``[[like this]]``;
``{{client}}``, ``{{seller}}``, ``{{valid_until}}`` and ``{{effective_date}}``
fill in from the SOW itself. Kept free of other domain imports.
"""

from __future__ import annotations

import re
from typing import Any

# A blank the seller must fill before sending, e.g. "[[cap amount]]".
PLACEHOLDER_RE = re.compile(r"\[\[([^\]]*)\]\]")
# A value filled from the SOW, e.g. "{{client}}".
TOKEN_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# A token whose SOW value is empty becomes this blank, so it's caught before sending.
_TOKEN_BLANKS = {
    "client": "client name",
    "seller": "SonaMation's legal name",
    "valid_until": "proposal validity date",
    "effective_date": "effective date",
}

# (key, title, body, included in new SOWs by default)
DEFAULT_CLAUSES: list[tuple[str, str, str, bool]] = [
    (
        "ip_ownership",
        "Intellectual Property & Ownership of Deliverables",
        "On full payment of the fees for a deliverable, ownership of that deliverable (the configuration, documentation "
        "and materials created specifically for {{client}} under this SOW) transfers to {{client}}. {{seller}} keeps "
        "ownership of its pre-existing materials, tools, templates and know-how, including anything it uses across "
        "clients, and grants {{client}} a non-exclusive, perpetual licence to use them as part of the deliverables. "
        "Third-party software, including HubSpot, remains subject to its own licence terms.",
        True,
    ),
    (
        "warranty",
        "Warranty & Defect Correction",
        "{{seller}} warrants that the Services will be performed in a professional manner consistent with generally "
        "accepted industry standards. For [[warranty period, e.g. 30 days]] after acceptance of each milestone, "
        "{{seller}} will correct at no additional charge any defect where a deliverable does not meet its acceptance "
        "criteria, provided the defect is reported in writing within that period and is not caused by changes made by "
        "{{client}} or third parties, or by changes to the HubSpot platform. Correction is {{client}}'s sole remedy for "
        "defective Services. No other warranties, express or implied, are given.",
        True,
    ),
    (
        "liability",
        "Limitation of Liability",
        "To the extent permitted by law, neither party is liable for indirect, incidental, special or consequential "
        "damages, including lost profits, revenue or data. Each party's total liability arising out of this SOW is "
        "limited to [[liability cap, e.g. the fees paid under this SOW in the 12 months before the claim]]. These "
        "limits do not apply to [[exclusions, e.g. breach of confidentiality, gross negligence, wilful misconduct or "
        "payment obligations]].",
        True,
    ),
    (
        "termination",
        "Termination",
        "Either party may terminate this SOW for cause if the other party materially breaches it and does not cure "
        "the breach within [[cure period, e.g. 15 days]] of written notice. Either party may terminate for "
        "convenience with [[notice period, e.g. 30 days]] written notice. On termination for any reason, {{client}} "
        "pays for Services performed and expenses incurred up to the termination date, with any milestone in progress "
        "charged in proportion to the work completed, plus [[termination fee, or 'no further fees']]; {{seller}} "
        "delivers all work completed to date.",
        True,
    ),
    (
        "governing_law",
        "Governing Law & Dispute Resolution",
        "This SOW is governed by the laws of [[governing state or country]], without regard to its conflict-of-law "
        "rules. The parties will first try to resolve any dispute through good-faith negotiation between their "
        "executive sponsors for [[negotiation period, e.g. 30 days]]. A dispute not resolved that way will be decided "
        "by [[forum, e.g. the courts of a named county and state, or binding arbitration under named rules]].",
        True,
    ),
    (
        "data_protection",
        "Data Protection & Personal Information",
        "{{client}} remains responsible for the personal data in its systems; {{seller}} processes personal data only "
        "to perform the Services and on {{client}}'s documented instructions. {{seller}} will access only the data it "
        "needs, keep it confidential, protect it with appropriate technical and organisational measures, and notify "
        "{{client}} within [[breach notification period, e.g. 72 hours]] of becoming aware of a personal-data breach. "
        "For data migrations, data moves only through methods {{client}} approves, extracts and working copies are "
        "deleted within [[deletion period, e.g. 30 days]] of acceptance, and {{client}} confirms it has the right to "
        "migrate the data. Where the law requires it, the parties will sign a data processing agreement.",
        True,
    ),
    (
        "force_majeure",
        "Force Majeure",
        "Neither party is liable for a delay or failure caused by events beyond its reasonable control, such as "
        "natural disasters, epidemics, war, government action, or failures of utilities, internet service or "
        "third-party platforms (including HubSpot outages). The affected party will notify the other promptly and "
        "resume as soon as possible, and the dates in this SOW move by the length of the delay. If the event lasts "
        "more than [[period, e.g. 30 days]], either party may end this SOW by written notice; fees for work performed "
        "to date remain payable.",
        True,
    ),
    (
        "non_solicitation",
        "Non-Solicitation",
        "During this SOW and for [[non-solicitation period, e.g. 12 months]] after it ends, neither party will "
        "directly solicit for employment any employee or contractor of the other party who worked on the Services, "
        "without the other party's written consent. General job advertisements not aimed at those people are not a "
        "breach.",
        True,
    ),
    (
        "entire_agreement",
        "Entire Agreement & Order of Precedence",
        "This SOW, including its schedules, is the entire agreement between the parties about its subject matter and "
        "replaces all prior proposals, discussions and understandings. It can be changed only by a written Change "
        "Request or amendment signed by both parties. If documents conflict, they apply in this order: [[order of "
        "precedence, e.g. (1) the Master Services Agreement, (2) this SOW, (3) approved Change Requests]].",
        True,
    ),
    (
        "msa_reference",
        "Master Services Agreement",
        "This SOW is issued under, and governed by, the Master Services Agreement between {{client}} and {{seller}} "
        "dated [[MSA date]]. Terms defined in that agreement have the same meaning in this SOW.",
        False,
    ),
    (
        "validity",
        "Proposal Validity & Effective Date",
        "This proposal is valid until {{valid_until}}. Once signed by both parties, this SOW takes effect on {{effective_date}}.",
        True,
    ),
]

BLANK_CLAUSE: dict[str, Any] = {"Key": "", "Title": "", "Body": "", "Include": True}


def default_clauses() -> list[dict[str, Any]]:
    """The standard set as SOW clause rows."""
    return [{"Key": key, "Title": title, "Body": body, "Include": on} for key, title, body, on in DEFAULT_CLAUSES]


def _token_values(proposal: dict[str, Any]) -> dict[str, str]:
    return {
        "client": str((proposal.get("client") or {}).get("company") or "").strip(),
        "seller": str((proposal.get("seller") or {}).get("company") or "").strip(),
        "valid_until": str(proposal.get("valid_until") or "").strip()[:10],
        "effective_date": str(proposal.get("effective_date") or "").strip()[:10],
    }


def render_clause(proposal: dict[str, Any], body: str) -> str:
    """A clause's text with ``{{tokens}}`` filled from the SOW. A token whose
    value is missing becomes a ``[[blank]]``; ``[[blanks]]`` stay as written."""
    values = _token_values(proposal)

    def fill(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in values:
            return m.group(0)
        return values[name] or f"[[{_TOKEN_BLANKS[name]}]]"

    return TOKEN_RE.sub(fill, body or "")


def included_clauses(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    """The SOW's switched-on clauses that have text, rendered."""
    out = []
    for row in proposal.get("clauses") or []:
        if not isinstance(row, dict) or row.get("Include") is False:
            continue
        title, body = str(row.get("Title") or "").strip(), str(row.get("Body") or "").strip()
        if title or body:
            out.append({**row, "Title": title or "Untitled clause", "Body": render_clause(proposal, body)})
    return out


def clause_blanks(proposal: dict[str, Any]) -> dict[str, list[str]]:
    """Unfilled ``[[blanks]]`` in the switched-on clauses, by clause title."""
    found: dict[str, list[str]] = {}
    for clause in included_clauses(proposal):
        blanks = list(dict.fromkeys(f"[[{b}]]" for b in PLACEHOLDER_RE.findall(clause["Body"] + " " + clause["Title"])))
        if blanks:
            found[clause["Title"]] = blanks
    return found


def add_missing_clauses(proposal_clauses: list[dict[str, Any]], library: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The SOW's clauses plus the library clauses it doesn't have yet (by key),
    each switched on as the library says."""
    have = {str(c.get("Key") or "") for c in proposal_clauses if c.get("Key")}
    return list(proposal_clauses) + [dict(c) for c in library if c.get("Key") and c["Key"] not in have]
