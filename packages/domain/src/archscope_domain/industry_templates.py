"""Industry templates (``config/industry_templates.yaml``): starting points
for the Discovery Call Assistant and the Proposal & SOW Builder by industry
and company size. Applying one fills only blanks — captured answers and
typed text are never replaced, and proposal rows already present are
skipped (the same merge as imports and suggestions)."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from archscope_domain import assist
from archscope_domain import discovery as dd
from archscope_domain import proposal as pp

TEMPLATES_PATH = Path(__file__).resolve().parent / "config" / "industry_templates.yaml"


class TemplateError(ValueError):
    """An unknown industry or size."""


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    description: str


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw: dict[str, Any] = yaml.safe_load(TEMPLATES_PATH.read_text(encoding="utf-8"))
    return raw


def industries() -> list[Choice]:
    return [Choice(key, t["label"], t.get("description", "")) for key, t in _load()["industries"].items()]


def sizes() -> list[Choice]:
    return [Choice(key, t["label"], t.get("description", "")) for key, t in _load()["sizes"].items()]


def _parts(industry: str, size: str | None) -> list[dict[str, Any]]:
    data = _load()
    if industry not in data["industries"]:
        raise TemplateError(f"Unknown industry template '{industry}'.")
    parts = [data["industries"][industry]]
    if size:
        if size not in data["sizes"]:
            raise TemplateError(f"Unknown company size '{size}'.")
        parts.append(data["sizes"][size])
    return parts


def discovery_answers(industry: str, size: str | None = None) -> dict[str, dict[str, list[str] | str]]:
    """The template's preset answers ({section: {question: options}}): the
    size's single-choice answers win; multi-choice lists are combined."""
    merged: dict[str, dict[str, list[str] | str]] = {}
    for part in _parts(industry, size):
        for section, answers in (part.get("discovery", {}).get("answers") or {}).items():
            target = merged.setdefault(section, {})
            for question, value in answers.items():
                current = target.get(question)
                if isinstance(value, list) and isinstance(current, list):
                    target[question] = current + [v for v in value if v not in current]
                else:
                    target[question] = value
    return merged


def apply_discovery(
    notes: dict[str, dict[str, Any]], business_type: str, industry: str, size: str | None = None
) -> tuple[dict[str, dict[str, Any]], str, int]:
    """``notes`` with the template's answers on every question not yet
    answered, and the business type if blank. Returns the notes, the
    business type and how many questions were filled."""
    out = copy.deepcopy(notes)
    filled = 0
    for section, answers in discovery_answers(industry, size).items():
        section_notes = out.setdefault(section, {"answers": {}, "notes": "", "edge_cases": ""})
        section_answers = section_notes.setdefault("answers", {})
        for question, value in answers.items():
            current = dd.as_answer(section_answers.get(question))
            if current["selected"] or str(current.get("notes", "")).strip() or str(current.get("other", "")).strip():
                continue
            section_answers[question] = {**current, "selected": list(value) if isinstance(value, list) else [value]}
            filled += 1
    if not business_type.strip():
        business_type = str(_parts(industry, size)[0].get("discovery", {}).get("business_type", ""))
    return out, business_type, filled


def proposal_rows(industry: str, size: str | None = None) -> dict[str, list[Any]]:
    """The template's proposal rows (Suggest-shaped), industry then size."""
    rows: dict[str, list[Any]] = {}
    for part in _parts(industry, size):
        for key, items in (part.get("proposal") or {}).items():
            rows.setdefault(key, []).extend(items)
    return rows


def apply_proposal(proposal: dict[str, Any], industry: str, size: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """``proposal`` (domain form) with the template's rows added where they
    aren't already, through the same merge as suggestions; the glossary too."""
    rows = proposal_rows(industry, size)
    merged, changed = assist.merge_proposal(proposal, {k: v for k, v in rows.items() if k != "glossary"})
    terms = [{"Term": g["term"], "Definition": g.get("definition", "")} for g in rows.get("glossary", []) if g.get("term")]
    if terms:
        before = len(pp.nonblank(merged.get("glossary", []), "Term"))
        merged["glossary"] = pp.merge_rows(merged.get("glossary", []), terms, "Term")
        if len(merged["glossary"]) != before:
            changed.append("glossary")
    return merged, changed
