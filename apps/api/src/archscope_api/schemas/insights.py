"""Where projects stand: stage, scoping progress, portal health, open tasks
(derived from each project's saved work; see services.project_insights)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import ApiModel


class PortalHealth(ApiModel):
    status: Literal["healthy", "needs_review", "not_started"] = Field(
        description="needs_review when the Portal Auditor found any High-severity issue; not_started before the first audit."
    )
    score: int | None = Field(
        None, description="0-100: 100 - 15 per High - 4 per Medium - 1 per Low finding. None before the first audit."
    )
    high: int = 0
    medium: int = 0
    low: int = 0


class ProjectInsight(ApiModel):
    project_id: str
    stage: Literal["Discover", "Assess", "Design", "Propose", "Deliver"] = Field(
        description="The furthest stage with a started tool."
    )
    progress: int = Field(ge=0, le=100, description="Scoping progress: % of the RevOps tools started.")
    tools_started: int
    tools_total: int
    open_tasks: int = Field(description="Unfinished tasks in the project's Tasks tracker.")
    health: PortalHealth


class DashboardPerson(ApiModel):
    id: str | None = Field(None, description="A workspace member's id; None for someone known only by name.")
    name: str


class Workstream(ApiModel):
    """A Tasks-tracker stage in progress."""

    stage: str
    title: str = Field(description="Its next open task.")
    people: list[DashboardPerson] = Field(description="The stage owner, then whoever ticked its tasks.")
    done: int
    total: int


class Completion(ApiModel):
    """The project's deliverables as percentages (they add up to 100)."""

    scoped: int = Field(description="Saved as a document.")
    in_progress: int = Field(description="Their tool has work, but no document is saved yet.")
    outstanding: int = Field(description="Not started.")
    deliverables: int = Field(description="How many deliverables there are in all.")


class StageDocuments(ApiModel):
    stage: Literal["Discover", "Assess", "Design", "Propose", "Deliver"]
    generated: int = Field(description="Saved documents for this stage's deliverables.")
    outstanding: int = Field(description="Deliverables of this stage with no saved document yet.")
    outstanding_names: list[str]


class Contributor(ApiModel):
    id: str
    name: str
    role: str = Field(description='"In charge", or their workspace role.')
    documents: int
    edits: int = Field(description="Tools they last saved work in.")


class ActivityItem(ApiModel):
    kind: Literal["document", "task", "audit", "edit"]
    title: str
    at: str = Field(description="ISO 8601 time.")
    by: str | None = Field(None, description="Who did it, by name.")


class ProjectDashboard(ApiModel):
    project_id: str
    insight: ProjectInsight
    continue_page: str = Field(description='The tool page to pick up from, e.g. "proposal" (under /projects/:id/).')
    continue_label: str
    team: list[DashboardPerson] = Field(description="Everyone on the project, person in charge first.")
    workstreams: list[Workstream]
    completion: Completion
    documents_by_stage: list[StageDocuments]
    contributors: list[Contributor]
    activity: list[ActivityItem]
    documents: int
