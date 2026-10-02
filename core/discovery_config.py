"""Discovery question bank — loads and validates
``config/discovery_options.yaml``.

The YAML is the single place discovery questions, their input type, and
their dropdown options are defined, so options can be standardized
without touching UI code. This module only turns it into
:class:`Question` objects and refuses a malformed file with a list of
exactly what's wrong (rather than the page failing somewhere deep in a
widget call).

Loads are cached on the file's modification time, so an edited YAML is
picked up on the next Streamlit rerun without restarting the app.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_OPTIONS_PATH = Path(__file__).resolve().parent.parent / "config" / "discovery_options.yaml"

INPUT_TEXT = "text"
INPUT_SELECT = "select"
INPUT_MULTISELECT = "multiselect"
INPUT_RADIO = "radio"
CHOICE_INPUTS = (INPUT_SELECT, INPUT_MULTISELECT, INPUT_RADIO)
INPUT_TYPES = (INPUT_TEXT, *CHOICE_INPUTS)

DEFAULT_OTHER_OPTION = "Other (specify)"

# Section-level fields share the per-section session-key namespace with
# question ids, so a question can't be called either of these.
RESERVED_IDS = frozenset({"notes", "edge_cases"})
_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class DiscoveryConfigError(ValueError):
    """``discovery_options.yaml`` is missing or malformed. ``problems``
    lists every issue found, each naming the offending entry."""

    def __init__(self, path: Path, problems: list[str]):
        self.path = path
        self.problems = problems
        super().__init__(f"{path.name}: " + "; ".join(problems))


@dataclass(frozen=True)
class Question:
    key: str
    label: str
    hint: str = ""
    input: str = INPUT_TEXT
    # Common answers from the YAML, without the "Other" option.
    options: tuple[str, ...] = ()

    @property
    def is_choice(self) -> bool:
        return self.input in CHOICE_INPUTS


@dataclass(frozen=True)
class QuestionBank:
    # Section name -> questions, in YAML order.
    sections: dict[str, list[Question]]
    other_option: str = DEFAULT_OTHER_OPTION

    def choices(self, question: Question) -> list[str]:
        """The options a widget for ``question`` offers: the YAML's
        options plus the "Other (specify)" fallback, last."""
        return [*question.options, self.other_option]


_cache: dict[Path, tuple[int, QuestionBank]] = {}


def load_question_bank(path: Optional[Path] = None) -> QuestionBank:
    """Parse and validate the question bank. Cached per file until the
    file's modification time changes. Raises :class:`DiscoveryConfigError`
    listing every problem if the file is missing or invalid."""
    path = Path(path or DEFAULT_OPTIONS_PATH)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        raise DiscoveryConfigError(path, [f"file not found at {path}"]) from None
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DiscoveryConfigError(path, [f"not valid YAML ({exc})"]) from None
    bank = parse_question_bank(raw, path=path)
    _cache[path] = (mtime, bank)
    return bank


def parse_question_bank(raw: Any, *, path: Path = DEFAULT_OPTIONS_PATH) -> QuestionBank:
    """Build a :class:`QuestionBank` from already-parsed YAML, collecting
    every problem before raising so one edit-reload cycle surfaces them all."""
    problems: list[str] = []
    if not isinstance(raw, dict) or not isinstance(raw.get("sections"), dict) or not raw["sections"]:
        raise DiscoveryConfigError(path, ["needs a top-level 'sections:' mapping with at least one section"])

    other_option = raw.get("other_option", DEFAULT_OTHER_OPTION)
    if not isinstance(other_option, str) or not other_option.strip():
        problems.append("'other_option' must be non-empty text")
        other_option = DEFAULT_OTHER_OPTION
    other_option = other_option.strip()

    sections: dict[str, list[Question]] = {}
    seen_ids: dict[str, str] = {}
    for section, entries in raw["sections"].items():
        if not isinstance(entries, list) or not entries:
            problems.append(f"section '{section}' must be a list of questions")
            continue
        questions = []
        for i, entry in enumerate(entries, start=1):
            where = f"{section} question #{i}"
            if not isinstance(entry, dict):
                problems.append(f"{where} must be a mapping with id/label/input")
                continue
            qid = entry.get("id")
            if isinstance(qid, str) and qid:
                where = f"{section} › {qid}"
            if not isinstance(qid, str) or not _ID_RE.match(qid):
                problems.append(f"{where}: 'id' must be snake_case (lowercase letters, digits, single underscores)")
                continue
            if qid in RESERVED_IDS:
                problems.append(f"{where}: '{qid}' is a reserved id")
                continue
            if qid in seen_ids:
                problems.append(f"{where}: duplicate id (also used in {seen_ids[qid]})")
                continue
            seen_ids[qid] = section

            label = entry.get("label")
            if not isinstance(label, str) or not label.strip():
                problems.append(f"{where}: 'label' is required")
                continue
            input_type = entry.get("input", INPUT_TEXT)
            if input_type not in INPUT_TYPES:
                problems.append(f"{where}: 'input' must be one of {', '.join(INPUT_TYPES)} (got {input_type!r})")
                continue
            hint = entry.get("hint") or ""
            if not isinstance(hint, str):
                problems.append(f"{where}: 'hint' must be text")
                continue

            options = entry.get("options") or []
            if not isinstance(options, list) or not all(isinstance(o, (str, int, float)) for o in options):
                problems.append(f"{where}: 'options' must be a list of text values")
                continue
            options = [str(o).strip() for o in options]
            if input_type == INPUT_TEXT and options:
                problems.append(f"{where}: a 'text' question can't have options — set 'input' to select/multiselect/radio")
                continue
            if input_type in CHOICE_INPUTS and not options:
                problems.append(f"{where}: a '{input_type}' question needs 'options'")
                continue
            if any(not o for o in options):
                problems.append(f"{where}: options can't be blank")
                continue
            dupes = sorted({o for o in options if options.count(o) > 1})
            if dupes:
                problems.append(f"{where}: duplicate option(s) {', '.join(dupes)}")
                continue
            # The fallback is appended automatically; tolerate it being listed.
            options = [o for o in options if o != other_option]

            questions.append(Question(qid, label.strip(), hint.strip(), input_type, tuple(options)))
        sections[str(section)] = questions

    if problems:
        raise DiscoveryConfigError(path, problems)
    return QuestionBank(sections=sections, other_option=other_option)
