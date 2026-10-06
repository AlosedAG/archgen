"""Proposal & SOW use cases (Module 10). Proposals are domain documents
(``dict[str, Any]``, versioned by ``schema_version``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from archscope_domain import proposal as dp
from archscope_domain.proposal_pdf import proposal_to_pdf

Proposal = dict[str, Any]


@dataclass(frozen=True)
class ProposalAnalysis:
    pricing: dict[str, Any]
    coverage: list[dict[str, str]]
    scope_by_status: dict[str, list[dict[str, Any]]]
    warnings: list[str]


def default_proposal() -> Proposal:
    return dp.default_proposal()


def analyse(proposal: Proposal) -> ProposalAnalysis:
    """Everything the builder shows next to the document, computed together
    so the numbers are always from the same version of the proposal."""
    return ProposalAnalysis(
        pricing=dp.pricing_summary(proposal),
        coverage=dp.requirement_coverage(proposal),
        scope_by_status=dp.scope_by_status(proposal),
        warnings=dp.validate(proposal),
    )


def import_wrd(proposal: Proposal, wrd: dict[str, list[dict[str, str]]]) -> Proposal:
    return dp.import_from_wrd(proposal, wrd)


def import_jep(proposal: Proposal, jep: dict[str, list[dict[str, str]]], prospect_name: str) -> Proposal:
    return dp.import_from_jep(proposal, jep, prospect_name=prospect_name)


def add_library_items(proposal: Proposal, items: list[str], status: str) -> Proposal:
    return dp.add_library_items(proposal, items, status)


def add_library_addons(proposal: Proposal, services: list[str]) -> Proposal:
    return dp.add_library_addons(proposal, services)


def draft_scope_from_requirements(proposal: Proposal) -> Proposal:
    return dp.scope_from_requirements(proposal)


def as_template(proposal: Proposal) -> Proposal:
    return dp.as_template(proposal)


def render_pdf(proposal: Proposal) -> bytes:
    return proposal_to_pdf(proposal)
