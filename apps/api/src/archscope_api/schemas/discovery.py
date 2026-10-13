"""Discovery Call Assistant (Module 11) contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from archscope_domain.discovery_config import QuestionBank as DomainQuestionBank

from .base import ApiModel
from .exports import ExportSection
from .stage_planner import PlannedStage

InputType = Literal["text", "select", "multiselect", "radio"]
HubSpotModule = Literal["Marketing Hub", "Sales Hub", "Service Hub", "Operations Hub", "Content Hub (CMS)", "Commerce Hub"]


class Question(ApiModel):
    id: str
    label: str
    hint: str = ""
    input: InputType
    options: list[str] = Field(default_factory=list, description="Common answers; the 'other' option is not included.")


class QuestionSection(ApiModel):
    name: str
    description: str = Field("", description="Optional one-line intro shown under the section heading.")
    questions: list[Question]


class QuestionBank(ApiModel):
    """The configured discovery questions, in asking order."""

    other_option: str = Field(description="Label of the free-text fallback appended to every choice question.")
    sections: list[QuestionSection]

    @classmethod
    def from_domain(cls, bank: DomainQuestionBank) -> QuestionBank:
        return cls(
            other_option=bank.other_option,
            sections=[
                QuestionSection(
                    name=name,
                    description=bank.descriptions.get(name, ""),
                    questions=[
                        Question(id=q.key, label=q.label, hint=q.hint, input=q.input, options=list(q.options)) for q in questions
                    ],
                )
                for name, questions in bank.sections.items()
            ],
        )


class Answer(ApiModel):
    """One question's structured answer. Text questions use ``notes``."""

    selected: list[str] = Field(default_factory=list)
    other: str = ""
    notes: str = Field("", max_length=20_000)
    flagged: bool = Field(False, description="Specialist marked this question for follow-up.")


class SectionNotes(ApiModel):
    answers: dict[str, Answer] = Field(default_factory=dict, description="Keyed by question id; missing ids are blank.")
    notes: str = Field("", max_length=20_000)
    edge_cases: str = Field("", max_length=20_000)


class DiscoveryNotes(ApiModel):
    client_name: str = Field("", max_length=200)
    business_type: str = Field("", max_length=200)
    sections: dict[str, SectionNotes] = Field(default_factory=dict, description="Keyed by section name.")

    def to_domain(self) -> dict[str, dict[str, Any]]:
        return {name: section.model_dump() for name, section in self.sections.items()}


class AnalysisPayload(ApiModel):
    """Exactly what is sent to the model for a business analysis —
    returned for preview/debugging without calling the model."""

    mode: Literal["business_analysis"]
    client: dict[str, str]
    sections: dict[str, dict[str, Any]]


class ClientExplainerRequest(ApiModel):
    modules: list[HubSpotModule] = Field(min_length=1)
    business_type: str = Field("", max_length=200)


class SuggestModulesRequest(ApiModel):
    business_analysis_markdown: str = Field(max_length=200_000)


class SuggestModulesResponse(ApiModel):
    modules: list[HubSpotModule]


# ---- Follow-up rules, checklist, build order --------------------------------


class FollowUpQuestion(Question):
    home_section: str = Field(description="Section the follow-up's answer is stored under in DiscoveryNotes.")


class RequiredTask(ApiModel):
    id: str
    label: str
    detail: str = ""


class BuildSectionInfo(ApiModel):
    id: str
    title: str


class BuildOrderSettings(ApiModel):
    project_types: list[str] = Field(description="Choices for the title; the first is the default.")
    statuses: list[str] = Field(description="Item statuses; the first is every new item's status.")
    done_status: str = Field(description="Status a ticked item gets.")
    sections: list[BuildSectionInfo]
    templates: dict[str, str] = Field(description="Reusable template id -> label.")


class DiscoveryConfig(ApiModel):
    """Everything the discovery form needs to render: the question bank,
    the follow-up questions rules can reveal, the tasks they can flag, and
    the build-order settings. The rules themselves stay server-side — the
    client asks ``/discovery/evaluate`` what its notes trigger."""

    question_bank: QuestionBank
    follow_ups: list[FollowUpQuestion]
    tasks: list[RequiredTask]
    build_order: BuildOrderSettings


class EvaluateRequest(DiscoveryNotes):
    project_type: str = Field("", max_length=200, description="Build-order project type; blank for the default.")
    done_build_items: list[str] = Field(default_factory=list, description="Ids of build-order items ticked as done.")
    stage_planner: list[PlannedStage] | None = Field(
        None, description="An applied Deal Stage Planner's stages; adds its build-order items."
    )


class FlaggedTask(ApiModel):
    task: RequiredTask
    section: str
    reasons: list[str] = Field(description="Why it's required — one per rule that flagged it.")


class BuildItem(ApiModel):
    id: str
    name: str
    sources: list[str]
    template: str | None
    template_label: str
    status: str
    done: bool


class BuildSection(ApiModel):
    id: str
    title: str
    items: list[BuildItem]


class BuildOrder(ApiModel):
    """The structured build order (``schema`` names the layout version) —
    the shape a later task-tool push would consume."""

    schema_: str = Field(alias="schema", serialization_alias="schema")
    title: str
    client: str
    project_type: str
    generated_on: str
    sections: list[BuildSection]


class Evaluation(ApiModel):
    """What a set of notes triggers, for every tab of the discovery page."""

    follow_ups: dict[str, list[str]] = Field(description="Question id -> ids of the follow-ups revealed under it, in order.")
    revealed_by: dict[str, list[str]] = Field(description="Follow-up id -> the selected options that revealed it.")
    tasks: list[FlaggedTask]
    checklist: list[ExportSection] = Field(description="Required tasks and scope items, ready for /exports/sections.")
    build_order: BuildOrder
    build_order_sections: list[ExportSection] = Field(description="The build order as export sections.")
