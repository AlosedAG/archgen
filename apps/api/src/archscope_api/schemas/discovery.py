"""Discovery Call Assistant (Module 11) contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from archscope_domain.discovery_config import QuestionBank as DomainQuestionBank

from .base import ApiModel

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
