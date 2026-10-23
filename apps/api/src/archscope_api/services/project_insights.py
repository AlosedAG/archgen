"""Where each project stands, derived from its saved work. This is the one
place the Projects cards and the project Dashboard get their numbers from.

- A RevOps tool counts as *started* once it has saved working state or a
  saved library document. Scoping progress is the share of tools started;
  a project's stage is the furthest stage with a started tool.
- Each tool produces deliverables (library documents of known types). A
  deliverable is *scoped* once one of its documents is saved, *in progress*
  while its tool has work but no document yet, otherwise *outstanding*.
- Portal health comes from the Portal Auditor's findings:
  100 - 15 per High - 4 per Medium - 1 per Low (never below 0). Any High
  finding means the project needs review; no audit yet means not started.

Nothing here talks to HubSpot: it only reads what the project has saved.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session

from ..persistence.models import Document, Project, ProjectState

STAGES = ("Discover", "Assess", "Design", "Propose", "Deliver")


@dataclass(frozen=True)
class Deliverable:
    name: str
    # Library document types that count as this deliverable.
    document_types: tuple[str, ...]


@dataclass(frozen=True)
class Tool:
    page: str  # its URL segment under /projects/:id/
    name: str
    stage: str
    module: str | None  # the saved state that shows work on it (None: only its documents do)
    deliverables: tuple[Deliverable, ...] = ()


def _one(name: str, *types: str) -> tuple[Deliverable, ...]:
    return (Deliverable(name, types or (name,)),)


# The RevOps tools in rail order. The two portal tools share the "portal" state.
TOOLS: tuple[Tool, ...] = (
    Tool(
        "discovery",
        "Discovery Call Assistant",
        "Discover",
        "discovery",
        (
            Deliverable("Discovery Checklist", ("Discovery Checklist",)),
            Deliverable("Business Analysis", ("Discovery Business Analysis",)),
            Deliverable("Client Explainer", ("Discovery Client Explainer",)),
            Deliverable("Company Overview", ("Company Overview",)),
            Deliverable("Build Order", ("Discovery Build Order",)),
        ),
    ),
    Tool(
        "stage-planner",
        "Deal Stage Planner",
        "Discover",
        "stage_planner",
        _one("Deal Stage Planner", "Pre-call Template — HubSpot Deal Stage Planner"),
    ),
    Tool(
        "requirements",
        "Requirements Document",
        "Discover",
        "requirements",
        _one("Requirements Document", "Written Requirements Document"),
    ),
    Tool("evaluation-plan", "Joint Evaluation Plan", "Discover", "evaluation_plan", _one("Joint Evaluation Plan")),
    Tool("portal-audit", "Portal Auditor", "Assess", "portal", _one("Portal Audit Findings")),
    Tool("property-audit", "Property Audit", "Assess", "portal:propertyAudit", _one("Property Audit")),
    Tool("documentation", "Documentation Generator", "Assess", None, _one("Documentation Pack")),
    Tool(
        "executive-report",
        "Executive Report",
        "Assess",
        None,
        _one("Executive Report", "Executive Report (Client)", "Executive Report (Internal)"),
    ),
    Tool("architecture", "Architecture Generator", "Design", "architecture", _one("Architecture Blueprint")),
    Tool("diagram", "Architecture Diagram", "Design", "diagram", _one("Architecture Diagram")),
    Tool("proposal", "Proposal & SOW Builder", "Propose", "proposal", _one("Proposal & SOW")),
    Tool("test-cases", "QA Reports", "Deliver", "test_cases", _one("Test Case Document")),
    Tool("schedule-planner", "Schedule Planner", "Deliver", "schedule"),
)

HealthStatus = Literal["healthy", "needs_review", "not_started"]


@dataclass(frozen=True)
class Health:
    status: HealthStatus
    score: int | None
    high: int = 0
    medium: int = 0
    low: int = 0


@dataclass(frozen=True)
class SavedDocument:
    document_type: str
    title: str
    created_by: str | None
    created_at: datetime


@dataclass
class ProjectFacts:
    """What one project has saved, loaded without reading large states in full."""

    modules: set[str] = field(default_factory=set)  # modules with saved work ("portal:propertyAudit" too)
    audited: bool = False
    severities: Counter[str] = field(default_factory=Counter)
    audited_at: str | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)
    task_stages: dict[str, Any] = field(default_factory=dict)  # the tracker's per-stage owner and dates
    documents: list[SavedDocument] = field(default_factory=list)
    # When each module was last saved, and by whom (for the activity feed and the team).
    edits: dict[str, tuple[datetime, str | None]] = field(default_factory=dict)


def load_facts(db: Session, workspace_id: str, project_ids: Iterable[str] | None = None) -> dict[str, ProjectFacts]:
    """Facts for the workspace's projects (or just ``project_ids``), in four small queries."""
    scope = select(Project.id).where(Project.workspace_id == workspace_id)
    if project_ids is not None:
        scope = scope.where(Project.id.in_(list(project_ids)))
    ids = list(db.scalars(scope))
    facts = {pid: ProjectFacts() for pid in ids}
    if not ids:
        return facts

    # Which modules hold more than an empty object (sizes are computed in the database).
    sizes = select(
        ProjectState.project_id,
        ProjectState.module,
        func.length(cast(ProjectState.data, Text)),
        ProjectState.updated_at,
        ProjectState.updated_by,
    ).where(ProjectState.project_id.in_(ids))
    for pid, module, size, updated_at, updated_by in db.execute(sizes):
        if (size or 0) > 2:
            facts[pid].edits[module] = (updated_at, updated_by)
            if module != "portal":  # the portal state is judged by what's in it, below
                facts[pid].modules.add(module)

    # The portal state carries a multi-MB snapshot: only pick out what's needed.
    data = ProjectState.data
    portal = select(
        ProjectState.project_id,
        data["findings"],
        data["auditedAt"].as_string(),
        data["snapshot"].as_string().is_not(None),
        data["propertyAudit"].as_string().is_not(None),
    ).where(ProjectState.project_id.in_(ids), ProjectState.module == "portal")
    for pid, findings, audited_at, has_snapshot, has_property_audit in db.execute(portal):
        f = facts[pid]
        findings = findings if isinstance(findings, list) else []
        if has_snapshot or audited_at or findings:
            f.modules.add("portal")
        if has_property_audit:
            f.modules.add("portal:propertyAudit")
        f.audited = bool(audited_at or findings)
        f.audited_at = audited_at or None
        f.severities = Counter(str(x.get("severity", "")) for x in findings if isinstance(x, dict))

    tasks = select(ProjectState.project_id, ProjectState.data).where(
        ProjectState.project_id.in_(ids), ProjectState.module == "tasks"
    )
    for pid, state in db.execute(tasks):
        state = state if isinstance(state, dict) else {}
        raw, stages = state.get("tasks"), state.get("stages")
        facts[pid].tasks = [t for t in raw if isinstance(t, dict)] if isinstance(raw, list) else []
        facts[pid].task_stages = stages if isinstance(stages, dict) else {}

    docs = select(Document.project_id, Document.document_type, Document.title, Document.created_by, Document.created_at).where(
        Document.project_id.in_(ids)
    )
    for pid, dtype, title, created_by, created_at in db.execute(docs):
        facts[pid].documents.append(SavedDocument(dtype, title, created_by, created_at))
    return facts


# ---- Derived figures ---------------------------------------------------------------


def started_tools(f: ProjectFacts) -> list[Tool]:
    """Tools with saved work or a saved deliverable."""
    saved_types = {d.document_type for d in f.documents}
    return [
        t
        for t in TOOLS
        if (t.module and t.module in f.modules) or any(dt in saved_types for d in t.deliverables for dt in d.document_types)
    ]


def stage_of(f: ProjectFacts) -> str:
    started = started_tools(f)
    return STAGES[max((STAGES.index(t.stage) for t in started), default=0)]


def progress_of(f: ProjectFacts) -> int:
    return round(100 * len(started_tools(f)) / len(TOOLS))


def health_of(f: ProjectFacts) -> Health:
    if not f.audited:
        return Health("not_started", None)
    high, medium, low = (f.severities.get(s, 0) for s in ("High", "Medium", "Low"))
    score = max(0, 100 - 15 * high - 4 * medium - low)
    return Health("needs_review" if high else "healthy", score, high, medium, low)


def open_tasks(f: ProjectFacts) -> int:
    return sum(1 for t in f.tasks if not t.get("done"))


@dataclass(frozen=True)
class Insight:
    stage: str
    progress: int
    tools_started: int
    tools_total: int
    open_tasks: int
    health: Health


def insight(f: ProjectFacts) -> Insight:
    return Insight(stage_of(f), progress_of(f), len(started_tools(f)), len(TOOLS), open_tasks(f), health_of(f))


def workspace_insights(db: Session, workspace_id: str) -> dict[str, Insight]:
    """Every project's headline figures, for the Projects page."""
    return {pid: insight(f) for pid, f in load_facts(db, workspace_id).items()}


# ---- The project dashboard ------------------------------------------------------------

# The Tasks tracker's stages, in order (Build and Test & launch both fall under Deliver).
TRACKER_STAGES = (
    ("discover", "Discover"),
    ("assess", "Assess"),
    ("design", "Design"),
    ("propose", "Propose"),
    ("build", "Build"),
    ("launch", "Test & launch"),
)
_FEED_LENGTH = 6
_WORKSTREAM_LENGTH = 3


@dataclass(frozen=True)
class Workstream:
    stage: str  # the tracker stage's name
    title: str  # its next open task
    owner_id: str | None
    people: tuple[str, ...]  # names of who ticked its tasks
    done: int
    total: int


@dataclass(frozen=True)
class StageDocuments:
    stage: str
    generated: int  # saved documents of this stage's deliverable types
    outstanding: int  # deliverables with no saved document yet
    deliverables: tuple[str, ...]  # the outstanding ones, by name


@dataclass(frozen=True)
class Completion:
    """Deliverables as shares of all of them (adds up to 100)."""

    scoped: int
    in_progress: int
    outstanding: int
    deliverables: int


@dataclass(frozen=True)
class Contributor:
    user_id: str
    documents: int
    edits: int
    in_charge: bool


@dataclass(frozen=True)
class Activity:
    kind: Literal["document", "task", "audit", "edit"]
    title: str
    at: datetime | str
    by: str | None  # a user id ("document", "edit") or a name ("task")


@dataclass(frozen=True)
class Dashboard:
    insight: Insight
    continue_page: str
    continue_label: str
    workstreams: tuple[Workstream, ...]
    completion: Completion
    documents_by_stage: tuple[StageDocuments, ...]
    contributors: tuple[Contributor, ...]
    activity: tuple[Activity, ...]
    documents: int


def _saved_types(f: ProjectFacts) -> set[str]:
    return {d.document_type for d in f.documents}


def continue_tool(f: ProjectFacts) -> Tool:
    """Where to pick up: the first tool of the current stage without saved work (or that stage's first tool)."""
    stage = stage_of(f)
    started = set(started_tools(f))
    in_stage = [t for t in TOOLS if t.stage == stage]
    return next((t for t in in_stage if t not in started), in_stage[0])


def workstreams(f: ProjectFacts) -> list[Workstream]:
    """Tracker stages in progress (a task ticked or a start date set, not all done), in order."""
    out: list[Workstream] = []
    for key, name in TRACKER_STAGES:
        tasks = [t for t in f.tasks if t.get("stage") == key]
        raw_meta = f.task_stages.get(key)
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        done = [t for t in tasks if t.get("done")]
        if tasks and len(done) == len(tasks):
            continue
        if not (done or meta.get("startedOn")):
            continue
        nxt = next((t for t in tasks if not t.get("done")), None)
        people = tuple(dict.fromkeys(str(t["doneBy"]) for t in done if t.get("doneBy") and t["doneBy"] != "From discovery"))
        out.append(
            Workstream(
                stage=name,
                title=str(nxt.get("title", "")) if nxt else f"{name} stage",
                owner_id=meta.get("ownerId") or None,
                people=people,
                done=len(done),
                total=len(tasks),
            )
        )
    return out[:_WORKSTREAM_LENGTH]


def documents_by_stage(f: ProjectFacts) -> list[StageDocuments]:
    saved = Counter(d.document_type for d in f.documents)
    out = []
    for stage in STAGES:
        delivs = [d for t in TOOLS if t.stage == stage for d in t.deliverables]
        generated = sum(saved[dt] for d in delivs for dt in d.document_types)
        missing = tuple(d.name for d in delivs if not any(saved[dt] for dt in d.document_types))
        out.append(StageDocuments(stage, generated, len(missing), missing))
    return out


def completion(f: ProjectFacts) -> Completion:
    saved, started = _saved_types(f), set(started_tools(f))
    scoped = in_progress = total = 0
    for tool in TOOLS:
        for d in tool.deliverables:
            total += 1
            if any(dt in saved for dt in d.document_types):
                scoped += 1
            elif tool in started:
                in_progress += 1
    pct = [round(100 * n / total) for n in (scoped, in_progress)]
    return Completion(pct[0], pct[1], 100 - pct[0] - pct[1], total)


_MODULE_TOOL = {t.module: t for t in TOOLS if t.module and ":" not in t.module}


def activity(f: ProjectFacts) -> list[Activity]:
    """The latest saved documents, ticked tasks, portal audit and tool edits, newest first."""
    items: list[Activity] = [Activity("document", d.title or d.document_type, d.created_at, d.created_by) for d in f.documents]
    for t in f.tasks:
        if t.get("done") and t.get("doneAt"):
            items.append(Activity("task", str(t.get("title", "Task")), str(t["doneAt"]), t.get("doneBy") or None))
    if f.audited and f.audited_at:
        n = sum(f.severities.values())
        items.append(Activity("audit", f"Portal audit: {n} issue{'s' if n != 1 else ''} found", f.audited_at, None))
    for module, (at, by) in f.edits.items():
        tool = _MODULE_TOOL.get(module)
        if tool:
            items.append(Activity("edit", f"{tool.name} updated", at, by))
    items.sort(key=lambda a: iso(a.at), reverse=True)
    return items[:_FEED_LENGTH]


def iso(at: datetime | str) -> str:
    """ISO strings and timestamps compare as UTC ISO text."""
    if isinstance(at, datetime):
        return at.isoformat().replace("+00:00", "Z")
    return at


def contributors(f: ProjectFacts, lead_id: str | None) -> list[Contributor]:
    """Everyone who saved a document or edited a tool here (and whoever is in charge), most documents first."""
    docs = Counter(d.created_by for d in f.documents if d.created_by)
    edits = Counter(by for _, by in f.edits.values() if by)
    ids = set(docs) | set(edits) | ({lead_id} if lead_id else set())
    people = [Contributor(i, docs[i], edits[i], i == lead_id) for i in ids]
    people.sort(key=lambda c: (-c.documents, -c.edits, not c.in_charge, c.user_id))
    return people


def dashboard(db: Session, workspace_id: str, project: Project) -> Dashboard:
    f = load_facts(db, workspace_id, [project.id])[project.id]
    tool = continue_tool(f)
    return Dashboard(
        insight=insight(f),
        continue_page=tool.page,
        continue_label=f"Continue in {tool.name}",
        workstreams=tuple(workstreams(f)),
        completion=completion(f),
        documents_by_stage=tuple(documents_by_stage(f)),
        contributors=tuple(contributors(f, project.lead_user_id)),
        activity=tuple(activity(f)),
        documents=len(f.documents),
    )
