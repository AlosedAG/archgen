"""Context-aware suggestions ("Fill from earlier steps" / "Suggest") contract.

The page sends what the project already holds (it has it loaded) plus its
own current values; the API asks the model and returns those values with
blanks filled — never anything the user typed overwritten."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import ApiModel
from .discovery import DiscoveryNotes
from .proposal import ProposalDocument
from .stage_planner import PlannedStage


class AssistContext(ApiModel):
    discovery: DiscoveryNotes | None = Field(None, description="The discovery call notes, if any.")
    business_analysis: str = Field("", max_length=60_000, description="The drafted business analysis (Markdown).")
    documents: dict[str, dict[str, list[dict[str, Any]]]] = Field(
        default_factory=dict,
        description='Earlier documents as {title: {section: rows}}, e.g. {"Requirements Document": {...}}.',
    )
    stage_planner: list[PlannedStage] = Field(default_factory=list, description="An applied Deal Stage Planner's stages.")


class StagePlannerAssistRequest(ApiModel):
    context: AssistContext
    stages: list[PlannedStage] = Field(default_factory=list, description="The planner's current stages (may be empty).")


class StagePlannerAssistResponse(ApiModel):
    stages: list[PlannedStage]
    filled: int = Field(description="How many cells were filled.")
    model: str


class ArchitectureInputs(ApiModel):
    standard_objects: list[str] = Field(default_factory=list)
    custom_object_keywords: list[str] = Field(default_factory=list)
    custom_object_notes: str = ""
    pipelines_required: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    currencies: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    other_integration_notes: str = ""
    record_volumes: dict[str, int] = Field(default_factory=dict)
    hubs_in_scope: list[str] = Field(default_factory=list)


class ArchitectureAssistRequest(ApiModel):
    context: AssistContext
    inputs: ArchitectureInputs


class ArchitectureAssistResponse(ApiModel):
    inputs: ArchitectureInputs
    added: int = Field(description="How many values were added.")
    model: str


class ProposalAssistRequest(ApiModel):
    context: AssistContext
    proposal: ProposalDocument


class ProposalAssistResponse(ApiModel):
    proposal: ProposalDocument
    changed: list[str] = Field(description="Proposal fields that received suggestions, e.g. executive_summary, scope.")
    model: str


# ---- Industry templates --------------------------------------------------------


class TemplateChoice(ApiModel):
    id: str
    label: str
    description: str = ""


class IndustryTemplates(ApiModel):
    industries: list[TemplateChoice]
    sizes: list[TemplateChoice]


class IndustryDiscoveryRequest(ApiModel):
    industry: str
    size: str | None = None
    notes: DiscoveryNotes


class IndustryDiscoveryResponse(ApiModel):
    notes: DiscoveryNotes
    filled: int = Field(description="How many unanswered questions received the template's answer.")


class IndustryProposalRequest(ApiModel):
    industry: str
    size: str | None = None
    proposal: ProposalDocument


class IndustryProposalResponse(ApiModel):
    proposal: ProposalDocument
    changed: list[str]


# ---- Project task tracker ------------------------------------------------------------


class TaskStub(ApiModel):
    stage: str
    title: str


class SuggestedTask(ApiModel):
    stage: str = Field(description="discover, assess, design, propose, build or launch.")
    title: str
    source: str = Field("", description="Why the task is needed, and where in the project that comes from.")


class ProjectTasksAssistRequest(ApiModel):
    context: AssistContext
    tasks: list[TaskStub] = Field(default_factory=list, description="Tasks already on the list (not suggested again).")


class ProjectTasksAssistResponse(ApiModel):
    tasks: list[SuggestedTask]
    model: str


# ---- Company overview ------------------------------------------------------------------


class CompanyOverviewRequest(ApiModel):
    website: str = Field(min_length=3, max_length=300)
    client_name: str = Field("", max_length=200)
    business_type: str = Field("", max_length=200)


class CompanyOverview(ApiModel):
    name: str = ""
    type: str = ""
    summary: str = ""
    audience: str = ""
    locations: str = ""
    offerings: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    things_to_know: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)


class CompanyOverviewResponse(ApiModel):
    overview: CompanyOverview
    website: str = Field(description="The address that was read.")
    model: str


# ---- Schedule Planner ------------------------------------------------------------------


class ScheduleSettings(ApiModel):
    """How the meetings should be scheduled (every field optional)."""

    start_date: str = Field("", max_length=10, description="First possible meeting date, yyyy-mm-dd.")
    go_live_date: str = Field("", max_length=10, description="Target go-live date, yyyy-mm-dd.")
    cadence: str = Field("", max_length=60, description="e.g. 'Weekly', 'Twice a week', 'Every two weeks'.")
    preferred_days: list[str] = Field(default_factory=list, max_length=7, description="Weekday names.")
    default_time: str = Field("", max_length=5, description="HH:MM, 24-hour.")
    duration_minutes: int | None = Field(None, ge=15, le=480)
    timezone: str = Field("", max_length=60)
    platform: str = Field("", max_length=60, description="Zoom, Google Meet, Microsoft Teams, phone, in person…")
    meeting_count: int | None = Field(None, ge=1, le=40, description="Roughly how many meetings to plan.")
    attendees: str = Field("", max_length=2000, description="Who usually attends, by role.")
    notes: str = Field("", max_length=4000, description="Scheduling constraints and preferences.")


class MeetingStub(ApiModel):
    title: str = Field(max_length=300)
    type: str = Field("", max_length=40)
    date: str = Field("", max_length=10)


class SuggestedMeeting(ApiModel):
    title: str
    type: str = Field(
        description="kickoff, discovery, requirements, design, build, data, training, uat, go_live, review or other."
    )
    stage: str = Field("", description="discover, assess, design, propose, build or launch (or empty).")
    week: int | None = Field(None, description="1-based week from the start date.")
    duration_minutes: int | None = None
    purpose: str = ""
    agenda: list[str] = Field(default_factory=list)
    prepare: list[str] = Field(default_factory=list)
    review: list[str] = Field(default_factory=list)
    explain: str = ""
    attendees: list[str] = Field(default_factory=list)


class ScheduleAssistRequest(ApiModel):
    context: AssistContext
    settings: ScheduleSettings = Field(default_factory=ScheduleSettings)
    meetings: list[MeetingStub] = Field(default_factory=list, max_length=100, description="Meetings already planned.")


class ScheduleAssistResponse(ApiModel):
    meetings: list[SuggestedMeeting]
    model: str


class MeetingContent(ApiModel):
    purpose: str = Field("", max_length=4000)
    agenda: list[str] = Field(default_factory=list, max_length=50)
    prepare: list[str] = Field(default_factory=list, max_length=50)
    review: list[str] = Field(default_factory=list, max_length=50)
    explain: str = Field("", max_length=8000)
    attendees: list[str] = Field(default_factory=list, max_length=50)
    follow_ups: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field("", max_length=8000)


class MeetingToPrepare(MeetingContent):
    title: str = Field(max_length=300)
    type: str = Field("", max_length=40)
    date: str = Field("", max_length=10)
    time: str = Field("", max_length=5)
    duration_minutes: int | None = Field(None, ge=15, le=480)


class ScheduleMeetingAssistRequest(ApiModel):
    context: AssistContext
    settings: ScheduleSettings = Field(default_factory=ScheduleSettings)
    meeting: MeetingToPrepare
    other_meetings: list[MeetingStub] = Field(default_factory=list, max_length=100)


class ScheduleMeetingAssistResponse(ApiModel):
    meeting: MeetingContent
    changed: list[str] = Field(description="The fields that got new content.")
    model: str
