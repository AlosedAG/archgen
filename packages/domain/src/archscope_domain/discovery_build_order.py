"""Implementation build order — loads and validates
``config/discovery_build_order.yaml`` and turns the confirmed scope
(required tasks + scope items from the discovery checklist, plus specific
answers) into a :class:`BuildOrder`: "[Client] — [Project Type] — Build
Order", with checkable items grouped under configurable sections and
items deployable from a reusable template tagged apart from
build-from-scratch ones.

:class:`BuildOrder` is plain data with a stable :meth:`BuildOrder.to_dict`
JSON shape (item ids from the YAML, sources, template, status) so it can
later be pushed to a task tool; nothing here talks to any external
system. :meth:`BuildOrder.to_sections` feeds the shared exporters.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from archscope_domain.discovery_checklist import ChecklistConfig
from archscope_domain.discovery_config import ID_RE, DiscoveryConfigError
from archscope_domain.discovery_rules import selected_options
from archscope_domain.exporters import Section

DEFAULT_BUILD_ORDER_PATH = Path(__file__).resolve().parent / "config" / "discovery_build_order.yaml"

# Identifies the JSON layout of BuildOrder.to_dict(), for whatever later
# consumes it (e.g. a ClickUp / HubSpot task push). Bump on breaking change.
SCHEMA_VERSION = "archscope.build_order/v1"

COL_DONE = "Done"
COL_ITEM = "Item"
COL_SOURCE = "Source"
COL_TEMPLATE = "Template"
COL_STATUS = "Status"
FROM_SCRATCH = "Build from scratch"
TEMPLATE_TAG = "TEMPLATE"
_OPTION = "{option}"


class DiscoveryBuildOrderError(DiscoveryConfigError):
    """``discovery_build_order.yaml`` is missing or malformed. ``problems``
    lists every issue found, each naming the offending entry."""


@dataclass(frozen=True)
class BuildSection:
    key: str
    title: str


@dataclass(frozen=True)
class ExtraItem:
    """A build item supplied from outside the YAML rules (e.g. an imported
    Deal Stage Planner). ``key`` must be stable — tick-marks refer to it."""

    key: str
    section: str
    name: str
    source: str
    template: str | None = None


@dataclass(frozen=True)
class ItemRule:
    """One ``items:`` entry. Exactly one of ``task`` / ``scope`` /
    ``answer_question`` is set."""

    key: str
    section: str
    name: str
    template: str | None = None
    task: str | None = None
    scope: str | None = None
    answer_question: str | None = None
    answer_values: tuple[str, ...] = ()


@dataclass
class BuildItem:
    id: str
    section: str
    name: str
    # Where it came from — a required task, scope item, or answer; several
    # when more than one trigger produced the same item.
    sources: list[str]
    template: str | None
    template_label: str
    status: str

    @property
    def is_template(self) -> bool:
        return self.template is not None


@dataclass
class BuildOrder:
    client: str
    project_type: str
    generated_on: str
    done_status: str
    # Section -> its items, template items first. Sections with no items
    # are kept so the document always shows every configured header.
    sections: list[tuple[BuildSection, list[BuildItem]]] = field(default_factory=list)

    @property
    def title(self) -> str:
        return f"{self.client or 'Client'} — {self.project_type} — Build Order"

    @property
    def items(self) -> list[BuildItem]:
        return [item for _, items in self.sections for item in items]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form — the shape an external task push would
        consume: sections with items carrying id, name, sources, template,
        status, and done."""
        return {
            "schema": SCHEMA_VERSION,
            "title": self.title,
            "client": self.client,
            "project_type": self.project_type,
            "generated_on": self.generated_on,
            "sections": [
                {
                    "id": section.key,
                    "title": section.title,
                    "items": [
                        {
                            "id": item.id,
                            "name": item.name,
                            "sources": list(item.sources),
                            "template": item.template,
                            "template_label": item.template_label,
                            "status": item.status,
                            "done": item.status == self.done_status,
                        }
                        for item in items
                    ],
                }
                for section, items in self.sections
            ],
        }

    def to_sections(self) -> list[Section]:
        """Export sections for the shared exporters: one per configured
        header, each row a checkable item with its source, template tag,
        and status."""
        return [
            (
                section.title,
                [
                    {
                        COL_DONE: "[x]" if item.status == self.done_status else "[ ]",
                        COL_ITEM: item.name,
                        COL_SOURCE: "; ".join(item.sources),
                        COL_TEMPLATE: f"{TEMPLATE_TAG}: {item.template_label}" if item.is_template else FROM_SCRATCH,
                        COL_STATUS: item.status,
                    }
                    for item in items
                ],
            )
            for section, items in self.sections
        ]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "item"


@dataclass(frozen=True)
class BuildOrderConfig:
    checklist: ChecklistConfig
    project_types: list[str]
    statuses: list[str]
    done_status: str
    sections: list[BuildSection]
    templates: dict[str, str]
    items: list[ItemRule]

    def build(
        self,
        notes: dict[str, dict[str, Any]],
        *,
        client: str = "",
        project_type: str = "",
        done_ids: set[str] | frozenset[str] = frozenset(),
        generated_on: str | None = None,
        extra_items: Sequence[ExtraItem] = (),
    ) -> BuildOrder:
        """The build order for these notes. ``done_ids`` are item ids the
        specialist ticked (they get ``done_status``); every other item
        gets the first status. ``extra_items`` are added after the YAML
        rules' items (and merged with any of the same name); ones naming
        an unknown section are skipped."""
        rules = self.checklist.rules
        evaluation = rules.evaluate(notes)
        flagged = {t.task.key: t.task.label for t in evaluation.tasks}
        shown = evaluation.revealed_ids
        picks = self.checklist.scope_picks(notes)
        by_section: dict[str, dict[str, BuildItem]] = {s.key: {} for s in self.sections}

        def add(item_id: str, rule: ItemRule, name: str, source: str) -> None:
            merged = by_section[rule.section]
            existing = merged.get(name.lower())
            if existing:
                if source not in existing.sources:
                    existing.sources.append(source)
                return
            merged[name.lower()] = BuildItem(
                id=item_id,
                section=rule.section,
                name=name,
                sources=[source],
                template=rule.template,
                template_label=self.templates.get(rule.template, "") if rule.template else "",
                status=self.done_status if item_id in done_ids else self.statuses[0],
            )

        for rule in self.items:
            if rule.task:
                if rule.task in flagged:
                    add(rule.key, rule, rule.name, f"Required task: {flagged[rule.task]}")
            elif rule.scope:
                for pick in picks:
                    if pick.question_id == rule.scope:
                        add(
                            f"{rule.key}__{_slug(pick.option)}",
                            rule,
                            rule.name.replace(_OPTION, pick.option),
                            f"Scope item: {pick.item}",
                        )
            elif rule.answer_question:
                qid = rule.answer_question
                if qid in rules.follow_ups and qid not in shown:
                    continue
                matched = [v for v in rule.answer_values if v in selected_options(notes, rules.section_of(qid), qid)]
                if matched:
                    question = rules.question(qid)
                    add(rule.key, rule, rule.name, f"{question.label if question else qid} → {', '.join(matched)}")

        for extra in extra_items:
            if extra.section in by_section:
                add(extra.key, ItemRule(extra.key, extra.section, extra.name, extra.template), extra.name, extra.source)

        return BuildOrder(
            client=client.strip(),
            project_type=project_type or self.project_types[0],
            generated_on=generated_on or date.today().isoformat(),
            done_status=self.done_status,
            sections=[
                (section, sorted(by_section[section.key].values(), key=lambda item: not item.is_template))
                for section in self.sections
            ],
        )


_cache: dict[Path, tuple[int, ChecklistConfig, BuildOrderConfig]] = {}


def load_build_order_config(checklist: ChecklistConfig, path: Path | None = None) -> BuildOrderConfig:
    """Parse and validate the build-order config against ``checklist`` (and
    its rules and question bank). Cached per file until its modification
    time (or the checklist config) changes. Raises
    :class:`DiscoveryBuildOrderError` listing every problem if the file is
    missing or invalid."""
    path = Path(path or DEFAULT_BUILD_ORDER_PATH)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        raise DiscoveryBuildOrderError(path, [f"file not found at {path}"]) from None
    cached = _cache.get(path)
    if cached and cached[0] == mtime and cached[1] is checklist:
        return cached[2]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DiscoveryBuildOrderError(path, [f"not valid YAML ({exc})"]) from None
    config = parse_build_order_config(raw, checklist, path=path)
    _cache[path] = (mtime, checklist, config)
    return config


def _text_list(raw: dict[str, Any], key: str, problems: list[str]) -> list[str]:
    value = raw.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        problems.append(f"'{key}' must be a non-empty list of text (quote Yes/No/True/False)")
        return []
    return [v.strip() for v in value]


def parse_build_order_config(raw: Any, checklist: ChecklistConfig, *, path: Path = DEFAULT_BUILD_ORDER_PATH) -> BuildOrderConfig:
    """Build :class:`BuildOrderConfig` from already-parsed YAML, collecting
    every problem before raising so one edit-reload cycle surfaces them all."""
    if not isinstance(raw, dict):
        raise DiscoveryBuildOrderError(path, ["needs top-level 'project_types', 'statuses', 'sections', and 'items'"])
    problems: list[str] = []
    rules = checklist.rules

    project_types = _text_list(raw, "project_types", problems)
    statuses = _text_list(raw, "statuses", problems)
    done_status = str(raw.get("done_status") or "")
    if statuses and done_status not in statuses:
        problems.append(f"'done_status' must be one of the statuses ({', '.join(statuses)})")

    sections: list[BuildSection] = []
    raw_sections = raw.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        problems.append("'sections' must be a non-empty list of {id, title}")
        raw_sections = []
    for i, entry in enumerate(raw_sections, start=1):
        where = f"sections #{i}"
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not ID_RE.match(entry["id"]):
            problems.append(f"{where}: needs a snake_case 'id'")
            continue
        if any(s.key == entry["id"] for s in sections):
            problems.append(f"{where}: duplicate id '{entry['id']}'")
            continue
        if not isinstance(entry.get("title"), str) or not entry["title"].strip():
            problems.append(f"{where} ({entry['id']}): 'title' is required")
            continue
        sections.append(BuildSection(entry["id"], entry["title"].strip()))
    section_ids = {s.key for s in sections}

    templates: dict[str, str] = {}
    raw_templates = raw.get("templates") or {}
    if not isinstance(raw_templates, dict):
        problems.append("'templates' must be a mapping of id -> label")
        raw_templates = {}
    for tid, label in raw_templates.items():
        if not isinstance(tid, str) or not ID_RE.match(tid) or not isinstance(label, str) or not label.strip():
            problems.append(f"templates › {tid}: needs a snake_case id and a text label")
            continue
        templates[tid] = label.strip()

    items: list[ItemRule] = []
    raw_items = raw.get("items") or []
    if not isinstance(raw_items, list):
        problems.append("'items' must be a list")
        raw_items = []
    scope_ids = {s.question_id for s in checklist.scope_sources}
    seen: set[str] = set()
    for i, entry in enumerate(raw_items, start=1):
        where = f"items #{i}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be a mapping with id/section/name and a trigger")
            continue
        key = entry.get("id")
        if isinstance(key, str) and key:
            where = f"items › {key}"
        if not isinstance(key, str) or not ID_RE.match(key):
            problems.append(f"{where}: 'id' must be snake_case (lowercase letters, digits, single underscores)")
            continue
        if key in seen:
            problems.append(f"{where}: duplicate id")
            continue
        seen.add(key)
        section = entry.get("section")
        if section not in section_ids:
            problems.append(f"{where}: 'section' must be one of {', '.join(sorted(section_ids))} (got {section!r})")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{where}: 'name' is required")
            continue
        template = entry.get("template")
        if template is not None and template not in templates:
            problems.append(f"{where}: unknown template {template!r}")
            continue
        triggers = [t for t in ("task", "scope", "answer") if entry.get(t) is not None]
        if len(triggers) != 1:
            problems.append(f"{where}: needs exactly one trigger — 'task', 'scope', or 'answer'")
            continue
        if _OPTION in name and triggers != ["scope"]:
            problems.append(f"{where}: '{_OPTION}' in 'name' only works with a 'scope' trigger")
            continue
        rule = ItemRule(key, section, name.strip(), template)
        if triggers == ["task"]:
            if entry["task"] not in rules.tasks:
                problems.append(f"{where}: task {entry['task']!r} isn't a task in discovery_rules.yaml")
                continue
            rule = ItemRule(key, section, rule.name, template, task=entry["task"])
        elif triggers == ["scope"]:
            if entry["scope"] not in scope_ids:
                problems.append(f"{where}: scope {entry['scope']!r} isn't a question listed in discovery_checklist.yaml")
                continue
            rule = ItemRule(key, section, rule.name, template, scope=entry["scope"])
        else:
            answer = entry["answer"]
            qid = answer.get("question_id") if isinstance(answer, dict) else None
            question = rules.question(qid) if isinstance(qid, str) else None
            if question is None or not question.is_choice:
                problems.append(f"{where}: answer needs a choice question_id from the question bank or follow-ups")
                continue
            values = answer.get("value")
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
                problems.append(f"{where}: answer 'value' must be an option, or a list of options")
                continue
            unknown = [v for v in values if v not in question.options]
            if unknown:
                problems.append(f"{where}: {', '.join(repr(v) for v in unknown)} isn't an option of '{qid}' (must match exactly)")
                continue
            rule = ItemRule(key, section, rule.name, template, answer_question=qid, answer_values=tuple(values))
        items.append(rule)

    if problems:
        raise DiscoveryBuildOrderError(path, problems)
    return BuildOrderConfig(
        checklist=checklist,
        project_types=project_types,
        statuses=statuses,
        done_status=done_status,
        sections=sections,
        templates=templates,
        items=items,
    )
