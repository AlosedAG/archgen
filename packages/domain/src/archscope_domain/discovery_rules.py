"""Discovery "gotcha" rules — loads and validates
``config/discovery_rules.yaml`` and evaluates it against live call notes.

A rule says: when question X has option Y selected, reveal these
follow-up questions and flag these required tasks. The rules, the
follow-up questions, and the tasks all live in the YAML so new gotchas
can be added without code changes; this module checks every reference
against the question bank (a typo'd option would otherwise make a rule
silently never fire) and works out, for a given set of notes, which
follow-ups are showing and which tasks are required.

Rules can chain — a trigger may be a follow-up question, which only
counts while that follow-up is revealed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from archscope_domain.discovery_config import (
    ID_RE,
    RESERVED_IDS,
    DiscoveryConfigError,
    Question,
    QuestionBank,
    parse_question_fields,
)

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "config" / "discovery_rules.yaml"


class DiscoveryRulesError(DiscoveryConfigError):
    """``discovery_rules.yaml`` is missing or malformed. ``problems``
    lists every issue found, each naming the offending entry."""


@dataclass(frozen=True)
class Task:
    key: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class Rule:
    question_id: str
    # The rule fires when any of these options is selected.
    values: tuple[str, ...]
    reveals: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlaggedTask:
    task: Task
    # Section of the first rule that flagged it — where the task is
    # reported in the AI payload.
    section: str
    # Why it's required, one per rule that flagged it, e.g.
    # "Where are their customers / contacts located? → EU / UK".
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Evaluation:
    """Which follow-ups are showing and which tasks are required, for one
    set of notes."""

    # Question id (bank or follow-up) -> follow-ups revealed under it, in
    # reveal order. Each follow-up appears under exactly one question.
    follow_ups: dict[str, list[Question]] = field(default_factory=dict)
    tasks: list[FlaggedTask] = field(default_factory=list)
    # Follow-up id -> the selected options that revealed it (e.g.
    # ("EU / UK",)), for "Revealed by …" labels.
    revealed_by: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def revealed_ids(self) -> set[str]:
        return {q.key for questions in self.follow_ups.values() for q in questions}


@dataclass(frozen=True)
class DiscoveryRules:
    bank: QuestionBank
    follow_ups: dict[str, Question]
    tasks: dict[str, Task]
    rules: list[Rule]
    # Follow-up id -> the section its answer is stored under (that of the
    # first rule, in file order, that can reveal it).
    home_sections: dict[str, str]

    def section_of(self, question_id: str) -> str | None:
        for section, questions in self.bank.sections.items():
            if any(q.key == question_id for q in questions):
                return section
        return self.home_sections.get(question_id)

    def question(self, question_id: str) -> Question | None:
        for questions in self.bank.sections.values():
            for q in questions:
                if q.key == question_id:
                    return q
        return self.follow_ups.get(question_id)

    def evaluate(self, notes: dict[str, dict[str, Any]]) -> Evaluation:
        """Fire every rule whose trigger question is showing and has a
        matching option selected, repeating until no new rule fires (so
        chained rules on revealed follow-ups are picked up)."""
        visible = {q.key for questions in self.bank.sections.values() for q in questions}
        follow_ups: dict[str, list[Question]] = {}
        revealed_by: dict[str, tuple[str, ...]] = {}
        tasks: dict[str, tuple[str, list[str]]] = {}
        fired = [False] * len(self.rules)
        changed = True
        while changed:
            changed = False
            for i, rule in enumerate(self.rules):
                if fired[i] or rule.question_id not in visible:
                    continue
                selected = selected_options(notes, self.section_of(rule.question_id), rule.question_id)
                matched = [v for v in rule.values if v in selected]
                if not matched:
                    continue
                fired[i] = changed = True
                for fid in rule.reveals:
                    if fid not in visible:
                        visible.add(fid)
                        follow_ups.setdefault(rule.question_id, []).append(self.follow_ups[fid])
                        revealed_by[fid] = tuple(matched)
                trigger = self.question(rule.question_id)
                reason = f"{trigger.label if trigger else rule.question_id} → {', '.join(matched)}"
                for tid in rule.flags:
                    _, reasons = tasks.setdefault(tid, (self.section_of(rule.question_id) or "", []))
                    if reason not in reasons:
                        reasons.append(reason)
        return Evaluation(
            follow_ups=follow_ups,
            revealed_by=revealed_by,
            tasks=[FlaggedTask(self.tasks[tid], section, tuple(reasons)) for tid, (section, reasons) in tasks.items()],
        )


def selected_options(notes: dict[str, dict[str, Any]], section: str | None, question_id: str) -> list[str]:
    """The options picked for a question. Plain-string answers (free text
    from before answers were structured) select nothing."""
    value = notes.get(section or "", {}).get("answers", {}).get(question_id)
    if not isinstance(value, dict):
        return []
    selected = value.get("selected") or []
    return [selected] if isinstance(selected, str) else [str(s) for s in selected]


_cache: dict[Path, tuple[int, QuestionBank, DiscoveryRules]] = {}


def load_discovery_rules(bank: QuestionBank, path: Path | None = None) -> DiscoveryRules:
    """Parse and validate the rules against ``bank``. Cached per file until
    its modification time (or the question bank) changes. Raises
    :class:`DiscoveryRulesError` listing every problem if the file is
    missing or invalid."""
    path = Path(path or DEFAULT_RULES_PATH)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        raise DiscoveryRulesError(path, [f"file not found at {path}"]) from None
    cached = _cache.get(path)
    if cached and cached[0] == mtime and cached[1] is bank:
        return cached[2]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DiscoveryRulesError(path, [f"not valid YAML ({exc})"]) from None
    rules = parse_discovery_rules(raw, bank, path=path)
    _cache[path] = (mtime, bank, rules)
    return rules


def parse_discovery_rules(raw: Any, bank: QuestionBank, *, path: Path = DEFAULT_RULES_PATH) -> DiscoveryRules:
    """Build :class:`DiscoveryRules` from already-parsed YAML, collecting
    every problem before raising so one edit-reload cycle surfaces them all."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise DiscoveryRulesError(path, ["needs top-level 'follow_ups:', 'tasks:', and 'rules:' entries"])
    problems: list[str] = []
    bank_sections = {q.key: section for section, questions in bank.sections.items() for q in questions}

    follow_ups: dict[str, Question] = {}
    raw_follow_ups = raw.get("follow_ups") or {}
    if not isinstance(raw_follow_ups, dict):
        problems.append("'follow_ups' must be a mapping of id -> question")
        raw_follow_ups = {}
    for fid, entry in raw_follow_ups.items():
        where = f"follow_ups › {fid}"
        if not isinstance(fid, str) or not ID_RE.match(fid):
            problems.append(f"{where}: id must be snake_case (lowercase letters, digits, single underscores)")
            continue
        if fid in RESERVED_IDS:
            problems.append(f"{where}: '{fid}' is a reserved id")
            continue
        if fid in bank_sections:
            problems.append(f"{where}: id is already a question in discovery_options.yaml ({bank_sections[fid]})")
            continue
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be a mapping with label/input")
            continue
        question = parse_question_fields(fid, entry, where, problems, other_option=bank.other_option)
        if question:
            follow_ups[fid] = question

    tasks: dict[str, Task] = {}
    raw_tasks = raw.get("tasks") or {}
    if not isinstance(raw_tasks, dict):
        problems.append("'tasks' must be a mapping of id -> task")
        raw_tasks = {}
    for tid, entry in raw_tasks.items():
        where = f"tasks › {tid}"
        if not isinstance(tid, str) or not ID_RE.match(tid):
            problems.append(f"{where}: id must be snake_case (lowercase letters, digits, single underscores)")
            continue
        if isinstance(entry, str):
            entry = {"label": entry}
        if not isinstance(entry, dict) or not isinstance(entry.get("label"), str) or not entry["label"].strip():
            problems.append(f"{where}: 'label' is required")
            continue
        detail = entry.get("detail") or ""
        if not isinstance(detail, str):
            problems.append(f"{where}: 'detail' must be text")
            continue
        tasks[tid] = Task(tid, entry["label"].strip(), detail.strip())

    rules: list[Rule] = []
    raw_rules = raw.get("rules")
    if raw_rules is None:
        raw_rules = []
    if not isinstance(raw_rules, list):
        problems.append("'rules' must be a list")
        raw_rules = []
    for i, entry in enumerate(raw_rules, start=1):
        rule = _parse_rule(entry, f"rule #{i}", bank, follow_ups, raw_follow_ups, tasks, raw_tasks, problems)
        if rule:
            rules.append(rule)

    # Where each follow-up's answer is stored: the section of the first
    # rule that can reveal it, resolved through chains.
    home_sections: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for rule in rules:
            section = bank_sections.get(rule.question_id) or home_sections.get(rule.question_id)
            if section is None:
                continue
            for fid in rule.reveals:
                if fid not in home_sections:
                    home_sections[fid] = section
                    changed = True
    for fid in follow_ups:
        if fid not in home_sections:
            problems.append(
                f"follow_ups › {fid}: never shown — no rule reveals it from a discovery_options.yaml question "
                "(directly or through other follow-ups)"
            )

    if problems:
        raise DiscoveryRulesError(path, problems)
    return DiscoveryRules(bank=bank, follow_ups=follow_ups, tasks=tasks, rules=rules, home_sections=home_sections)


def _id_list(entry: dict[str, Any], name: str, where: str, problems: list[str]) -> list[str] | None:
    value = entry.get(name) or []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        problems.append(f"{where}: '{name}' must be a list of ids")
        return None
    return value


def _parse_rule(
    entry: Any,
    where: str,
    bank: QuestionBank,
    follow_ups: dict[str, Question],
    raw_follow_ups: dict[str, Any],
    tasks: dict[str, Task],
    raw_tasks: dict[str, Any],
    problems: list[str],
) -> Rule | None:
    if not isinstance(entry, dict) or not isinstance(entry.get("trigger"), dict):
        problems.append(f"{where}: needs a 'trigger:' with question_id and value")
        return None
    trigger = entry["trigger"]
    qid = trigger.get("question_id")
    if isinstance(qid, str) and qid:
        where = f"{where} ({qid})"
    question = next((q for qs in bank.sections.values() for q in qs if q.key == qid), None) or follow_ups.get(qid)
    if question is None:
        if qid in raw_follow_ups:
            return None  # The follow-up itself is invalid; already reported.
        problems.append(f"{where}: trigger question_id {qid!r} isn't a question or follow-up id")
        return None
    if not question.is_choice:
        problems.append(f"{where}: trigger question '{qid}' is a text question — triggers need a choice question")
        return None

    values = trigger.get("value")
    if isinstance(values, (str, int, float)) and not isinstance(values, bool):
        values = [values]
    if (
        not isinstance(values, list)
        or not values
        or any(isinstance(v, bool) or not isinstance(v, (str, int, float)) for v in values)
    ):
        problems.append(f"{where}: trigger 'value' must be an option, or a list of options (quote Yes/No/True/False)")
        return None
    values = [str(v).strip() for v in values]
    valid = {*question.options, bank.other_option}
    unknown = [v for v in values if v not in valid]
    if unknown:
        problems.append(f"{where}: {', '.join(repr(v) for v in unknown)} isn't an option of '{qid}' (must match exactly)")
        return None

    reveals = _id_list(entry, "reveals", where, problems)
    flags = _id_list(entry, "flags", where, problems)
    if reveals is None or flags is None:
        return None
    if not reveals and not flags:
        problems.append(f"{where}: needs 'reveals' and/or 'flags'")
        return None
    missing = [f for f in reveals if f not in raw_follow_ups] + [t for t in flags if t not in raw_tasks]
    if missing:
        problems.append(f"{where}: unknown follow-up / task id(s) {', '.join(missing)}")
        return None
    if any(f not in follow_ups for f in reveals) or any(t not in tasks for t in flags):
        return None  # References an invalid follow-up or task; already reported.
    return Rule(qid, tuple(values), tuple(reveals), tuple(flags))
