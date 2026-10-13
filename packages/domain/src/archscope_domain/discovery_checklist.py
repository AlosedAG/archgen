"""Discovery required-tasks checklist — loads and validates
``config/discovery_checklist.yaml`` and turns live call notes into the
checklist the specialist reviews and exports.

Two parts, each an export :data:`~archscope_domain.exporters.Section`:

- **Required tasks** — the tasks ``discovery_rules.yaml`` flagged for the
  client's answers (see :mod:`archscope_domain.discovery_rules`).
- **Scope items** — one row per option picked on the questions the YAML
  lists, e.g. each integration the client needs.

Every row carries the task, why it's there (the answer that put it on the
list), and a blank "Status / Notes" column for the specialist to fill in
after export.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from archscope_domain.discovery_config import DiscoveryConfigError
from archscope_domain.discovery_rules import DiscoveryRules
from archscope_domain.exporters import Section

DEFAULT_CHECKLIST_PATH = Path(__file__).resolve().parent / "config" / "discovery_checklist.yaml"

REQUIRED_TASKS_TITLE = "Required tasks"
SCOPE_ITEMS_TITLE = "Scope items"
COL_TASK = "Task"
COL_WHY = "Why it's required"
COL_STATUS = "Status / Notes"


class DiscoveryChecklistError(DiscoveryConfigError):
    """``discovery_checklist.yaml`` is missing or malformed. ``problems``
    lists every issue found, each naming the offending entry."""


@dataclass(frozen=True)
class ScopeSource:
    """A question whose picked options each become a scope item."""

    question_id: str
    name: str
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopePick:
    """One scope item: the option picked (or "Other" text), the checklist
    item name (e.g. "Integration: Salesforce"), and why it's there."""

    question_id: str
    option: str
    item: str
    why: str


@dataclass(frozen=True)
class ChecklistConfig:
    rules: DiscoveryRules
    scope_sources: list[ScopeSource]

    def build(self, notes: dict[str, dict[str, Any]]) -> list[Section]:
        """The checklist for these notes: the Required tasks section, then
        the Scope items section. Either may be empty (no rows)."""
        evaluation = self.rules.evaluate(notes)
        tasks = [
            {
                COL_TASK: f"{flagged.task.label} — {flagged.task.detail}" if flagged.task.detail else flagged.task.label,
                COL_WHY: "; ".join(flagged.reasons),
                COL_STATUS: "",
            }
            for flagged in evaluation.tasks
        ]
        scope = [{COL_TASK: pick.item, COL_WHY: pick.why, COL_STATUS: ""} for pick in self.scope_picks(notes)]
        return [(REQUIRED_TASKS_TITLE, tasks), (SCOPE_ITEMS_TITLE, scope)]

    def scope_picks(self, notes: dict[str, dict[str, Any]]) -> list[ScopePick]:
        """Every scope item these notes produce, in config order — the
        Scope items rows, kept structured for the build order."""
        picks: list[ScopePick] = []
        shown = self.rules.evaluate(notes).revealed_ids
        other_option = self.rules.bank.other_option
        for source in self.scope_sources:
            if source.question_id in self.rules.follow_ups and source.question_id not in shown:
                continue
            question = self.rules.question(source.question_id)
            answer = notes.get(self.rules.section_of(source.question_id) or "", {}).get("answers", {}).get(source.question_id)
            if question is None or not isinstance(answer, dict):
                continue
            selected = answer.get("selected") or []
            for option in [selected] if isinstance(selected, str) else selected:
                if option in source.exclude:
                    continue
                if option == other_option:
                    option = str(answer.get("other") or "").strip()
                    if not option:
                        continue
                    why = f"{question.label} → Other: {option}"
                else:
                    why = f"{question.label} → {option}"
                picks.append(ScopePick(source.question_id, option, f"{source.name}: {option}", why))
        return picks


_cache: dict[Path, tuple[int, DiscoveryRules, ChecklistConfig]] = {}


def load_checklist_config(rules: DiscoveryRules, path: Path | None = None) -> ChecklistConfig:
    """Parse and validate the checklist config against ``rules`` (and its
    question bank). Cached per file until its modification time (or the
    rules) change. Raises :class:`DiscoveryChecklistError` listing every
    problem if the file is missing or invalid."""
    path = Path(path or DEFAULT_CHECKLIST_PATH)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        raise DiscoveryChecklistError(path, [f"file not found at {path}"]) from None
    cached = _cache.get(path)
    if cached and cached[0] == mtime and cached[1] is rules:
        return cached[2]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DiscoveryChecklistError(path, [f"not valid YAML ({exc})"]) from None
    config = parse_checklist_config(raw, rules, path=path)
    _cache[path] = (mtime, rules, config)
    return config


def parse_checklist_config(raw: Any, rules: DiscoveryRules, *, path: Path = DEFAULT_CHECKLIST_PATH) -> ChecklistConfig:
    """Build :class:`ChecklistConfig` from already-parsed YAML, collecting
    every problem before raising so one edit-reload cycle surfaces them all."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise DiscoveryChecklistError(path, ["needs a top-level 'scope_items:' list"])
    entries = raw.get("scope_items") or []
    if not isinstance(entries, list):
        raise DiscoveryChecklistError(path, ["'scope_items' must be a list"])
    problems: list[str] = []
    sources: list[ScopeSource] = []
    seen: set[str] = set()
    for i, entry in enumerate(entries, start=1):
        where = f"scope_items #{i}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be a mapping with question_id")
            continue
        qid = entry.get("question_id")
        if isinstance(qid, str) and qid:
            where = f"{where} ({qid})"
        question = rules.question(qid) if isinstance(qid, str) else None
        if not isinstance(qid, str) or question is None:
            problems.append(f"{where}: question_id {qid!r} isn't a question or follow-up id")
            continue
        if not question.is_choice:
            problems.append(f"{where}: '{qid}' is a text question — scope items need a choice question")
            continue
        if qid in seen:
            problems.append(f"{where}: '{qid}' is listed more than once")
            continue
        seen.add(qid)
        name = entry.get("name") or question.label
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{where}: 'name' must be text")
            continue
        exclude = entry.get("exclude") or []
        if isinstance(exclude, str):
            exclude = [exclude]
        if not isinstance(exclude, list) or not all(isinstance(o, str) for o in exclude):
            problems.append(f"{where}: 'exclude' must be a list of options (quote Yes/No/True/False)")
            continue
        unknown = [o for o in exclude if o not in question.options]
        if unknown:
            problems.append(f"{where}: {', '.join(repr(o) for o in unknown)} isn't an option of '{qid}' (must match exactly)")
            continue
        sources.append(ScopeSource(qid, name.strip(), tuple(exclude)))
    if problems:
        raise DiscoveryChecklistError(path, problems)
    return ChecklistConfig(rules=rules, scope_sources=sources)
