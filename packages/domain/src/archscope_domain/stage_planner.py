"""HubSpot Deal Stage Planner — the pre-call template reps send to clients,
and the importer that reads a filled-out copy back.

Everything about the template's layout lives in
``config/stage_planner.yaml``: the row labels (and the aliases accepted on
import), the placeholder / "N/A" markers, the example stages written to
the blank template, and how parsed stages map onto the rest of the app.

- :func:`build_template` writes the downloadable ``.xlsx``.
- :func:`parse_stage_planner` reads a filled-out one into a
  :class:`StagePlanner`. It matches rows by their column-A label (clients
  insert and delete rows), reads however many stage columns were filled
  in, and collects everything odd it skipped as ``warnings`` rather than
  failing.
- The ``to_*`` functions turn a (reviewed) planner into the Discovery
  Processes answer, the Architecture Generator's deal pipeline, deal
  properties and workflows, and build-order items. Nothing here talks to
  HubSpot — this is input ingestion only.
"""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from archscope_domain.discovery_build_order import BuildOrderConfig, ExtraItem
from archscope_domain.discovery_config import DiscoveryConfigError
from archscope_domain.models import PipelineDef, PropertyDef, StageDef, WorkflowSuggestion
from archscope_domain.rules import RulesEngine

DEFAULT_STAGE_PLANNER_PATH = Path(__file__).resolve().parent / "config" / "stage_planner.yaml"

ROW_KEYS = ("name", "forecast", "entry_criteria", "exit_criteria", "actions", "automations")
XLSX_MAGIC = b"PK\x03\x04"


class StagePlannerConfigError(DiscoveryConfigError):
    """``stage_planner.yaml`` is missing or malformed. ``problems`` lists
    every issue found, each naming the offending entry."""


class StagePlannerParseError(ValueError):
    """The uploaded file can't be read as a Stage Planner at all (not an
    .xlsx, or no stage-name row). Smaller issues are warnings instead."""


# ---- Data ------------------------------------------------------------------


@dataclass
class PlannedStage:
    """One stage column of the planner."""

    name: str
    forecast: float | None = None  # 0–100
    entry_criteria: str = ""
    exit_criteria: str = ""
    actions: str = ""
    automations: str = ""
    # Deal properties a rep must fill in at this stage, in row order.
    fields: list[str] = field(default_factory=list)


@dataclass
class StagePlanner:
    stages: list[PlannedStage] = field(default_factory=list)
    # Everything the parser skipped or guessed at, for the reviewer.
    warnings: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StagePlanner:
        """Rebuild from :meth:`to_dict` output (e.g. session state or an edited review table)."""
        return cls(
            stages=[
                PlannedStage(
                    name=str(s.get("name") or "").strip(),
                    forecast=_to_float(s.get("forecast")),
                    entry_criteria=str(s.get("entry_criteria") or "").strip(),
                    exit_criteria=str(s.get("exit_criteria") or "").strip(),
                    actions=str(s.get("actions") or "").strip(),
                    automations=str(s.get("automations") or "").strip(),
                    fields=[str(f).strip() for f in s.get("fields") or [] if str(f).strip()],
                )
                for s in data.get("stages") or []
                if str(s.get("name") or "").strip()
            ],
            warnings=[str(w) for w in data.get("warnings") or []],
            source=str(data.get("source") or ""),
        )


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---- Config ----------------------------------------------------------------


@dataclass(frozen=True)
class RowSpec:
    key: str
    label: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PropertyTypeRule:
    keywords: tuple[str, ...]
    type: str
    field_type: str


@dataclass(frozen=True)
class StagePlannerConfig:
    sheet_name: str
    rows: list[RowSpec]
    fields_label: str
    fields_aliases: tuple[str, ...]
    field_row_label: str
    field_template_rows: int
    placeholders: tuple[str, ...]
    empty_markers: tuple[str, ...]
    item_separators: tuple[str, ...]
    template: dict[str, Any]
    pipeline_object: str
    pipeline_name: str
    won_keywords: tuple[str, ...]
    won_forecast: float | None
    lost_keywords: tuple[str, ...]
    lost_forecast: float | None
    discovery_section: str
    discovery_question_id: str
    property_types: list[PropertyTypeRule]
    default_property_type: tuple[str, str]
    property_group: str
    existing_properties: dict[str, str]
    build_order: dict[str, dict[str, str]]

    def row(self, key: str) -> RowSpec:
        return next(r for r in self.rows if r.key == key)


_cache: dict[Path, tuple[int, int, StagePlannerConfig]] = {}


def load_stage_planner_config(build_order: BuildOrderConfig, path: Path | None = None) -> StagePlannerConfig:
    """Parse and validate ``stage_planner.yaml`` against the build-order
    sections and the question bank. Cached per file until it changes.
    Raises :class:`StagePlannerConfigError` listing every problem."""
    path = Path(path or DEFAULT_STAGE_PLANNER_PATH)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        raise StagePlannerConfigError(path, [f"file not found at {path}"]) from None
    cached = _cache.get(path)
    if cached and cached[0] == mtime and cached[1] == id(build_order):
        return cached[2]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StagePlannerConfigError(path, [f"not valid YAML ({exc})"]) from None
    config = parse_stage_planner_config(raw, build_order, path=path)
    _cache[path] = (mtime, id(build_order), config)
    return config


def _text_tuple(value: Any, where: str, problems: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, (str, int, float)) for v in value):
        problems.append(f"{where}: must be a list of text")
        return ()
    return tuple(str(v) for v in value)


def parse_stage_planner_config(
    raw: Any, build_order: BuildOrderConfig, *, path: Path = DEFAULT_STAGE_PLANNER_PATH
) -> StagePlannerConfig:
    """Build :class:`StagePlannerConfig` from parsed YAML, collecting every problem before raising."""
    if not isinstance(raw, dict):
        raise StagePlannerConfigError(path, ["needs top-level 'rows', 'fields_section', 'template' and 'mapping'"])
    problems: list[str] = []

    rows: list[RowSpec] = []
    for i, entry in enumerate(raw.get("rows") or [], start=1):
        if not isinstance(entry, dict) or entry.get("key") not in ROW_KEYS or not isinstance(entry.get("label"), str):
            problems.append(f"rows #{i}: needs a 'label' and a 'key' that is one of {', '.join(ROW_KEYS)}")
            continue
        if any(r.key == entry["key"] for r in rows):
            problems.append(f"rows #{i}: key '{entry['key']}' is listed twice")
            continue
        rows.append(
            RowSpec(
                entry["key"],
                entry["label"].strip(),
                _text_tuple(entry.get("aliases"), f"rows › {entry['key']} aliases", problems),
            )
        )
    if not any(r.key == "name" for r in rows):
        problems.append("rows: the 'name' row (stage names) is required")

    fields_raw = raw.get("fields_section") or {}
    if not isinstance(fields_raw, dict) or not isinstance(fields_raw.get("label"), str):
        problems.append("fields_section: needs a 'label'")
        fields_raw = {"label": "Fields to Fill Out"}
    field_row_label = str(fields_raw.get("row_label") or "Field {n}")
    if "{n}" not in field_row_label:
        problems.append("fields_section › row_label: must contain {n}")

    template = raw.get("template") or {}
    if not isinstance(template, dict) or not isinstance(template.get("title"), str):
        problems.append("template: needs a 'title'")
        template = {"title": "Deal Stage Planner"}
    for i, stage in enumerate(template.get("stages") or [], start=1):
        if not isinstance(stage, dict) or not str(stage.get("name") or "").strip():
            problems.append(f"template › stages #{i}: needs a 'name'")
        elif stage.get("forecast") is not None and _to_float(stage["forecast"]) is None:
            problems.append(f"template › stages › {stage['name']}: 'forecast' must be a number")

    mapping = raw.get("mapping") or {}
    if not isinstance(mapping, dict):
        problems.append("mapping: must be a mapping")
        mapping = {}
    won = mapping.get("closed_won") or {}
    lost = mapping.get("closed_lost") or {}
    discovery = mapping.get("discovery") or {}
    section = str(discovery.get("section") or "")
    question_id = str(discovery.get("question_id") or "")
    bank = build_order.checklist.rules.bank
    if section not in bank.sections:
        problems.append(f"mapping › discovery › section: {section!r} isn't a discovery section")
    elif not any(q.key == question_id and not q.is_choice for q in bank.sections[section]):
        problems.append(f"mapping › discovery › question_id: {question_id!r} isn't a text question in {section}")

    property_types: list[PropertyTypeRule] = []
    for i, rule in enumerate(mapping.get("property_types") or [], start=1):
        if not isinstance(rule, dict) or not rule.get("type") or not rule.get("field_type"):
            problems.append(f"mapping › property_types #{i}: needs keywords, type and field_type")
            continue
        keywords = _text_tuple(rule.get("keywords"), f"mapping › property_types #{i} keywords", problems)
        property_types.append(PropertyTypeRule(tuple(k.lower() for k in keywords), str(rule["type"]), str(rule["field_type"])))
    default_type = mapping.get("default_property_type") or {"type": "string", "field_type": "text"}

    existing = mapping.get("existing_properties") or {}
    if not isinstance(existing, dict):
        problems.append("mapping › existing_properties: must be a mapping of label -> property name")
        existing = {}

    build = mapping.get("build_order") or {}
    section_ids = {s.key for s in build_order.sections}
    for kind in ("pipeline", "property", "automation", "action", "record_page"):
        entry = build.get(kind)
        if entry is None:
            continue
        if not isinstance(entry, dict) or entry.get("section") not in section_ids or not entry.get("name"):
            problems.append(
                f"mapping › build_order › {kind}: needs a 'name' and a 'section' from discovery_build_order.yaml "
                f"({', '.join(sorted(section_ids))})"
            )

    fields_aliases = _text_tuple(fields_raw.get("aliases"), "fields_section › aliases", problems)
    placeholders = _text_tuple(raw.get("placeholders"), "placeholders", problems)
    empty_markers = _text_tuple(raw.get("empty_markers"), "empty_markers", problems)
    separators = _text_tuple(raw.get("item_separators"), "item_separators", problems) or (";",)
    won_keywords = _text_tuple(won.get("name_keywords"), "mapping › closed_won › name_keywords", problems)
    lost_keywords = _text_tuple(lost.get("name_keywords"), "mapping › closed_lost › name_keywords", problems)

    if problems:
        raise StagePlannerConfigError(path, problems)
    return StagePlannerConfig(
        sheet_name=str(raw.get("sheet_name") or "Planner"),
        rows=rows,
        fields_label=fields_raw["label"].strip(),
        fields_aliases=fields_aliases,
        field_row_label=field_row_label,
        field_template_rows=int(fields_raw.get("template_rows") or 7),
        placeholders=placeholders,
        empty_markers=empty_markers,
        item_separators=separators,
        template=template,
        pipeline_object=str(mapping.get("pipeline_object") or "Deal"),
        pipeline_name=str(mapping.get("pipeline_name") or "Deal Pipeline"),
        won_keywords=tuple(k.lower() for k in won_keywords),
        won_forecast=_to_float(won.get("forecast")),
        lost_keywords=tuple(k.lower() for k in lost_keywords),
        lost_forecast=_to_float(lost.get("forecast")),
        discovery_section=section,
        discovery_question_id=question_id,
        property_types=property_types,
        default_property_type=(str(default_type.get("type", "string")), str(default_type.get("field_type", "text"))),
        property_group=str(mapping.get("property_group") or "stage_requirements"),
        existing_properties={_norm(k): str(v) for k, v in existing.items()},
        build_order={k: {"section": str(v["section"]), "name": str(v["name"])} for k, v in build.items() if isinstance(v, dict)},
    )


# ---- Parsing ---------------------------------------------------------------


def _norm(label: Any) -> str:
    """Label as compared: case-folded, whitespace collapsed, trailing ':' dropped."""
    return re.sub(r"\s+", " ", str(label or "")).strip().rstrip(":").strip().casefold()


def _clean(value: Any, config: StagePlannerConfig) -> str:
    """A cell as text: whitespace tidied; "N/A"-style markers become ""."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in str(value).splitlines()).strip()
    lowered = text.casefold()
    for marker in config.empty_markers:
        m = marker.casefold()
        if lowered == m or re.match(rf"^{re.escape(m)}[\s\-—–:,.]", lowered):
            return ""
    return text


def _forecast(value: Any) -> tuple[float | None, bool]:
    """A forecast cell as (number, was a fraction like 0.4 or a "%" string).
    Returns (None, False) when it isn't a number."""
    if value is None or value == "":
        return None, False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), False
    text = str(value).strip().replace(",", ".")
    percent = text.endswith("%")
    try:
        return float(text.rstrip("%").strip()), percent
    except ValueError:
        return None, False


def parse_stage_planner(content: bytes, config: StagePlannerConfig, *, source: str = "") -> StagePlanner:
    """Read a filled-out Stage Planner .xlsx. Raises
    :class:`StagePlannerParseError` only when it isn't a readable planner
    at all; everything else becomes a warning on the result."""
    if not content.startswith(XLSX_MAGIC):
        raise StagePlannerParseError("That file isn't an .xlsx workbook. Upload the Stage Planner as Excel (.xlsx).")
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=False)
    except Exception as exc:  # openpyxl raises a variety of types on corrupt files
        raise StagePlannerParseError(f"The workbook couldn't be opened ({type(exc).__name__}).") from None

    labels = {key: {_norm(r.label), *(_norm(a) for a in r.aliases)} for r in config.rows for key in [r.key]}
    fields_labels = {_norm(config.fields_label), *(_norm(a) for a in config.fields_aliases)}

    def label_rows(ws: Worksheet) -> dict[int, str]:
        return {
            row: _norm(ws.cell(row=row, column=1).value)
            for row in range(1, ws.max_row + 1)
            if _norm(ws.cell(row=row, column=1).value)
        }

    sheet = next((ws for ws in workbook.worksheets if _norm(ws.title) == _norm(config.sheet_name)), None)
    if sheet is None or not any(v in labels["name"] for v in label_rows(sheet).values()):
        sheet = next((ws for ws in workbook.worksheets if any(v in labels["name"] for v in label_rows(ws).values())), None)
    if sheet is None:
        name_label = config.row("name").label
        raise StagePlannerParseError(f"No sheet has a '{name_label}' row in column A, so this doesn't look like a Stage Planner.")

    warnings: list[str] = []
    rows = label_rows(sheet)
    found: dict[str, int] = {}
    fields_row: int | None = None
    for row, label in rows.items():
        if label in fields_labels and fields_row is None:
            fields_row = row
            continue
        for key, accepted in labels.items():
            if label in accepted:
                if key in found:
                    warnings.append(f"Row {row} repeats the '{config.row(key).label}' label — used row {found[key]}.")
                else:
                    found[key] = row
    for spec in config.rows:
        if spec.key != "name" and spec.key not in found:
            warnings.append(f"No '{spec.label}' row found — left blank for every stage.")
    field_rows: list[int] = []
    if fields_row is None:
        warnings.append(f"No '{config.fields_label}' section found — no deal properties imported.")
    else:
        known = set(found.values())
        field_rows = [
            row
            for row in range(fields_row + 1, sheet.max_row + 1)
            if row not in known
            and (
                rows.get(row)
                or any(sheet.cell(row=row, column=c).value not in (None, "") for c in range(2, sheet.max_column + 1))
            )
        ]

    name_row = found["name"]
    placeholders = {_norm(p) for p in config.placeholders}
    stages: list[PlannedStage] = []
    raw_forecasts: list[tuple[PlannedStage, float, bool, str]] = []
    seen: dict[str, str] = {}
    for col in range(2, sheet.max_column + 1):
        letter = get_column_letter(col)
        header = _clean(sheet.cell(row=name_row, column=col).value, config)
        detail_rows = [found[k] for k in found if k != "name"] + field_rows
        has_detail = any(_clean(sheet.cell(row=r, column=col).value, config) for r in detail_rows)
        if not header or _norm(header) in placeholders:
            if has_detail and not (header and _norm(header) in placeholders):
                warnings.append(f"Column {letter} has details but no stage name — skipped.")
            elif has_detail:
                warnings.append(f"Column {letter} still says '{header}' but has details — skipped; give it a stage name.")
            continue
        stage = PlannedStage(name=header)
        for key in ("entry_criteria", "exit_criteria", "actions", "automations"):
            if key in found:
                setattr(stage, key, _clean(sheet.cell(row=found[key], column=col).value, config))
        if "forecast" in found:
            cell = sheet.cell(row=found["forecast"], column=col).value
            number, is_percent = _forecast(cell)
            if number is None and _clean(cell, config):
                warnings.append(f"'{header}' (column {letter}): forecast {cell!r} isn't a number — left blank.")
            elif number is not None:
                raw_forecasts.append((stage, number, is_percent, letter))
        for row in field_rows:
            value = _clean(sheet.cell(row=row, column=col).value, config)
            if value and value not in stage.fields:
                stage.fields.append(value)
        if _norm(header) in seen:
            warnings.append(
                f"'{header}' appears twice (columns {seen[_norm(header)]} and {letter}) — HubSpot needs unique stage names."
            )
        seen.setdefault(_norm(header), letter)
        stages.append(stage)

    # Forecasts written as fractions (0.4) rather than percentages (40):
    # treat them all as fractions only when none is above 1.
    as_fraction = bool(raw_forecasts) and all(n <= 1 and not pct for _, n, pct, _ in raw_forecasts)
    for stage, number, _, letter in raw_forecasts:
        percent = number * 100 if as_fraction else number
        if not 0 <= percent <= 100:
            warnings.append(f"'{stage.name}' (column {letter}): forecast {number:g} is outside 0–100% — left blank.")
            continue
        stage.forecast = round(percent, 2)
    if as_fraction:
        warnings.append("Forecasts were written as fractions (e.g. 0.4) and were read as percentages (40%).")
    if not stages:
        warnings.append("No stages found — fill in at least one stage name in the stage-name row.")

    return StagePlanner(stages=stages, warnings=warnings, source=source or sheet.title)


# ---- Mapping ---------------------------------------------------------------


def split_items(text: str, config: StagePlannerConfig) -> list[str]:
    """A Desired Actions / Automations cell as separate items."""
    pattern = "|".join(re.escape(s) for s in config.item_separators)
    items = [re.sub(r"\s+", " ", part).strip(" .-") for part in re.split(pattern, text)]
    return [i[:1].upper() + i[1:] for i in items if i]


def _closed_state(stage: PlannedStage, config: StagePlannerConfig) -> tuple[bool, bool]:
    """(is_closed, is_won) for a stage, from its name, then its forecast."""
    name = stage.name.casefold()
    if any(k in name for k in config.won_keywords):
        return True, True
    if any(k in name for k in config.lost_keywords):
        return True, False
    if config.won_forecast is not None and stage.forecast == config.won_forecast:
        return True, True
    if config.lost_forecast is not None and stage.forecast == config.lost_forecast:
        return True, False
    return False, False


def stage_description(stage: PlannedStage) -> str:
    parts = []
    if stage.entry_criteria:
        parts.append(f"Entry: {stage.entry_criteria}")
    if stage.exit_criteria:
        parts.append(f"Exit: {stage.exit_criteria}")
    return " | ".join(parts)


def to_pipeline(planner: StagePlanner, config: StagePlannerConfig) -> PipelineDef:
    """The deal pipeline: stages in column order, forecast % as probability
    (0–1), entry / exit criteria as the stage description."""
    stages = []
    for order, stage in enumerate(planner.stages):
        is_closed, is_won = _closed_state(stage, config)
        stages.append(
            StageDef(
                name=stage.name,
                order=order,
                is_closed=is_closed,
                is_won=is_won,
                probability=None if stage.forecast is None else round(stage.forecast / 100, 4),
                description=stage_description(stage),
            )
        )
    return PipelineDef(object_type=config.pipeline_object, name=config.pipeline_name, stages=stages)


def _slug(label: str) -> str:
    text = label.casefold().replace("%", " pct ").replace("&", " and ").replace("/", " ")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "field"


@dataclass(frozen=True)
class PlannedProperty:
    """A "Field to Fill Out", with every stage that requires it."""

    label: str
    stages: tuple[str, ...]
    # The HubSpot property it maps to when it's one of HubSpot's own (e.g. closedate).
    existing: str = ""
    definition: PropertyDef | None = None


def to_deal_properties(planner: StagePlanner, config: StagePlannerConfig) -> list[PlannedProperty]:
    """Every distinct field label, first appearance first, tagged with the
    stages that require it. HubSpot's own deal properties are mapped, not
    re-created."""
    order: list[str] = []
    stages_by_label: dict[str, list[str]] = {}
    display: dict[str, str] = {}
    for stage in planner.stages:
        for label in stage.fields:
            key = _norm(label)
            if key not in stages_by_label:
                order.append(key)
                stages_by_label[key] = []
                display[key] = label
            if stage.name not in stages_by_label[key]:
                stages_by_label[key].append(stage.name)
    result = []
    for key in order:
        label, stages = display[key], tuple(stages_by_label[key])
        existing = config.existing_properties.get(key, "")
        if existing:
            result.append(PlannedProperty(label, stages, existing=existing))
            continue
        rule = next((r for r in config.property_types if any(k in key for k in r.keywords)), None)
        prop_type, field_type = (rule.type, rule.field_type) if rule else config.default_property_type
        result.append(
            PlannedProperty(
                label,
                stages,
                definition=PropertyDef(
                    name=_slug(label),
                    label=label,
                    type=prop_type,
                    field_type=field_type,
                    group=config.property_group,
                    description=f"Required at stage: {', '.join(stages)} (from the Deal Stage Planner).",
                ),
            )
        )
    return result


def to_workflows(planner: StagePlanner, config: StagePlannerConfig, rules: RulesEngine | None = None) -> list[WorkflowSuggestion]:
    """One suggested workflow per Automations item, triggered by the deal
    entering that stage, with the usual overwrite-risk check."""
    rules = rules or RulesEngine()
    workflows = []
    for stage in planner.stages:
        for item in split_items(stage.automations, config):
            is_risk, reason = rules.is_overwrite_risk(item)
            workflows.append(
                WorkflowSuggestion(
                    name=f"{config.pipeline_object} | {stage.name}: {item}",
                    object_type=config.pipeline_object,
                    trigger=f"{config.pipeline_object} enters the '{stage.name}' stage",
                    action_summary=item,
                    overwrite_risk=is_risk,
                    risk_reason=reason,
                )
            )
    return workflows


def to_build_items(planner: StagePlanner, config: StagePlannerConfig) -> list[ExtraItem]:
    """Build-order items: the pipeline, each new deal property, each
    automation and desired action, and the record-page update."""
    spec = config.build_order
    source = "Deal Stage Planner"
    items: list[ExtraItem] = []
    if not planner.stages:
        return items
    if "pipeline" in spec:
        names = " → ".join(s.name for s in planner.stages)
        items.append(
            ExtraItem(
                "planner_pipeline",
                spec["pipeline"]["section"],
                spec["pipeline"]["name"].format(count=len(planner.stages)),
                f"{source}: {names}",
            )
        )
    properties = to_deal_properties(planner, config)
    if "property" in spec:
        for prop in properties:
            if prop.definition:
                items.append(
                    ExtraItem(
                        f"planner_property__{prop.definition.name}",
                        spec["property"]["section"],
                        spec["property"]["name"].format(label=prop.label),
                        f"{source}: required at {', '.join(prop.stages)}",
                    )
                )
    for kind, attr in (("automation", "automations"), ("action", "actions")):
        if kind not in spec:
            continue
        for stage in planner.stages:
            for item in split_items(getattr(stage, attr), config):
                items.append(
                    ExtraItem(
                        f"planner_{kind}__{_slug(stage.name)}__{_slug(item)}",
                        spec[kind]["section"],
                        spec[kind]["name"].format(stage=stage.name, item=item),
                        f"{source}: {stage.name} stage",
                    )
                )
    if "record_page" in spec and properties:
        items.append(
            ExtraItem(
                "planner_record_page",
                spec["record_page"]["section"],
                spec["record_page"]["name"],
                f"{source}: {len(properties)} stage-required properties",
            )
        )
    return items


def to_discovery_answer(planner: StagePlanner) -> str:
    """The Processes answer: stage names in order with their forecast."""
    return " → ".join(f"{s.name} ({s.forecast:g}%)" if s.forecast is not None else s.name for s in planner.stages)


NOTES_START = "[Deal Stage Planner]"
NOTES_END = "[/Deal Stage Planner]"


def to_discovery_notes(planner: StagePlanner, config: StagePlannerConfig) -> str:
    """A notes block with each stage's criteria, actions, automations and
    required fields, between markers so a re-import replaces it."""
    lines = [NOTES_START]
    for stage in planner.stages:
        lines.append(f"{stage.name}" + (f" — {stage.forecast:g}%" if stage.forecast is not None else ""))
        for label, value in (
            ("Entry", stage.entry_criteria),
            ("Exit", stage.exit_criteria),
            ("Actions", stage.actions),
            ("Automations", stage.automations),
            ("Required fields", ", ".join(stage.fields)),
        ):
            if value:
                lines.append(f"  {label}: {value}")
    lines.append(NOTES_END)
    return "\n".join(lines)


def merge_notes(existing: str, block: str) -> str:
    """Put the planner block into a notes field, replacing an earlier one."""
    pattern = re.compile(re.escape(NOTES_START) + r".*?" + re.escape(NOTES_END), re.S)
    if pattern.search(existing or ""):
        return pattern.sub(lambda _: block, existing)
    return f"{existing.rstrip()}\n\n{block}" if (existing or "").strip() else block


# ---- Template --------------------------------------------------------------

_NAVY, _ORANGE, _ORANGE_SOFT = "FF2D3E50", "FFFF7A59", "FFFF9A7A"
_ALT, _WHITE, _BLANK = "FFF5F8FA", "FFFFFFFF", "FFF7F7F7"
_FIELD_HEAD, _FIELD_A, _FIELD_B, _FIELD_BLANK = "FFFFE8E0", "FFFFF0EB", "FFFFF8F5", "FFF5EDE9"
_GREY_LINE, _LIGHT_LINE, _SUBTLE = "FFCFD8DC", "FFECEFF1", "FF455A64"


def _fill(rgb: str) -> PatternFill:
    return PatternFill("solid", fgColor=rgb)


def _side(style: str, rgb: str) -> Side:
    return Side(style=style, color=rgb)


def build_template(config: StagePlannerConfig) -> bytes:
    """The blank-ish pre-call template: Instructions + Planner sheets,
    pre-filled with the example stages and blank columns to add more."""
    tpl = config.template
    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    planner = wb.create_sheet(config.sheet_name)

    # Instructions sheet
    ins.column_dimensions["A"].width = 2
    ins.column_dimensions["B"].width = 72
    ins.merge_cells("A1:B1")
    ins["A1"] = tpl.get("instructions_title") or f"{tpl['title']} — Instructions"
    ins["A1"].font = Font(name="Arial", size=14, bold=True, color=_WHITE)
    ins["A1"].fill = _fill(_NAVY)
    ins["A1"].alignment = Alignment(vertical="center", wrap_text=True)
    ins.row_dimensions[1].height = 36
    box = Border(*(_side("thin", _GREY_LINE) for _ in range(4)))
    row = 3
    for block in tpl.get("instructions") or []:
        head, body = ins.cell(row=row, column=2), ins.cell(row=row + 1, column=2)
        head.value, body.value = block.get("heading", ""), block.get("text", "")
        head.font = Font(name="Arial", size=10, bold=True, color=_WHITE)
        head.fill = _fill(_ORANGE)
        body.font = Font(name="Arial", size=10, color=_NAVY)
        body.fill = _fill(_ALT)
        for cell, valign in ((head, "center"), (body, "top")):
            cell.alignment = Alignment(vertical=valign, wrap_text=True)
            cell.border = box
        ins.row_dimensions[row].height = 21.75
        ins.row_dimensions[row + 1].height = 43.5
        ins.row_dimensions[row + 2].height = 4.5
        row += 3

    # Planner sheet
    stages = list(tpl.get("stages") or [])
    blank_cols = int(tpl.get("blank_stage_columns") or 0)
    n_fields = max([config.field_template_rows, *(len(s.get("fields") or []) for s in stages)])
    last_col = 1 + len(stages) + blank_cols
    last_letter = get_column_letter(last_col)
    planner.column_dimensions["A"].width = 28
    for col in range(2, last_col + 1):
        planner.column_dimensions[get_column_letter(col)].width = 26

    for r, (value, size, italic, fill, color, height) in enumerate(
        [
            (tpl["title"], 15, False, _NAVY, _WHITE, 37.5),
            (tpl.get("subtitle", ""), 9, True, "FFECEFF1", _SUBTLE, 18),
        ],
        start=1,
    ):
        planner.merge_cells(f"A{r}:{last_letter}{r}")
        cell = planner.cell(row=r, column=1, value=value)
        cell.font = Font(name="Arial", size=size, bold=not italic, italic=italic, color=color)
        cell.fill = _fill(fill)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        planner.row_dimensions[r].height = height
    for col in range(1, last_col + 1):
        planner.cell(row=3, column=col).fill = _fill(_ORANGE_SOFT)
    planner.row_dimensions[3].height = 3.75

    label_border = Border(left=_side("medium", _ORANGE), bottom=_side("thin", _GREY_LINE))
    cell_border = Border(left=_side("thin", _LIGHT_LINE), bottom=_side("medium", _ORANGE_SOFT))
    heights = {
        "name": 27.75,
        "forecast": 21.75,
        "entry_criteria": 63.75,
        "exit_criteria": 63.75,
        "actions": 72,
        "automations": 72,
    }
    row = 4
    for spec in config.rows:
        label = planner.cell(row=row, column=1, value=spec.label)
        orange = spec.key in ("name", "forecast")
        label.font = Font(name="Arial", size=10, bold=True, color=_WHITE)
        label.fill = _fill(_ORANGE if orange else _NAVY)
        label.alignment = Alignment(vertical="center", wrap_text=True)
        label.border = label_border
        for col in range(2, last_col + 1):
            idx = col - 2
            cell = planner.cell(row=row, column=col)
            cell.border = cell_border
            cell.alignment = Alignment(vertical="center" if spec.key == "name" else "top", wrap_text=True)
            if idx < len(stages):
                value = stages[idx].get(spec.key)
                cell.value = value if value not in (None, "") else None
                cell.fill = _fill(_ALT if idx % 2 == 0 else _WHITE)
                cell.font = Font(name="Arial", size=11 if spec.key == "name" else 9, bold=spec.key == "name", color=_NAVY)
            else:
                cell.fill = _fill(_BLANK)
                if spec.key == "name":
                    cell.value = config.placeholders[0] if config.placeholders else None
                    cell.font = Font(name="Arial", size=10, italic=True, color=_GREY_LINE)
        planner.row_dimensions[row].height = heights.get(spec.key, 40)
        row += 1

    head = planner.cell(row=row, column=1, value=config.fields_label)
    head_border = Border(*(_side("thin", _ORANGE_SOFT) for _ in range(4)))
    for col in range(1, last_col + 1):
        cell = planner.cell(row=row, column=col)
        cell.fill = _fill(_FIELD_HEAD)
        cell.border = head_border
    head.font = Font(name="Arial", size=9, bold=True, color=_NAVY)
    head.alignment = Alignment(vertical="center")
    planner.row_dimensions[row].height = 19.5
    row += 1
    field_border = Border(left=_side("thin", _LIGHT_LINE), bottom=_side("medium", _ORANGE))
    for n in range(1, n_fields + 1):
        label = planner.cell(row=row, column=1, value=config.field_row_label.format(n=n))
        label.font = Font(name="Arial", size=9, italic=True, color=_SUBTLE)
        label.fill = _fill(_ALT)
        label.alignment = Alignment(vertical="center")
        label.border = label_border
        for col in range(2, last_col + 1):
            idx = col - 2
            cell = planner.cell(row=row, column=col)
            cell.border = field_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if idx < len(stages):
                fields = stages[idx].get("fields") or []
                cell.value = fields[n - 1] if n <= len(fields) else None
                cell.fill = _fill(_FIELD_A if idx % 2 == 0 else _FIELD_B)
                cell.font = Font(name="Arial", size=9, color=_NAVY)
            else:
                cell.fill = _fill(_FIELD_BLANK)
        planner.row_dimensions[row].height = 21.75
        row += 1
    for col in range(1, last_col + 1):
        planner.cell(row=row, column=col).fill = _fill(_ORANGE)
    planner.row_dimensions[row].height = 4.5

    planner.freeze_panes = "B4"
    wb.active = wb.worksheets.index(planner)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
