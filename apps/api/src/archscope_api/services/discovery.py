"""Discovery Call Assistant use cases (Module 11)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from archscope_domain import discovery as dd
from archscope_domain.discovery_build_order import BuildOrder, BuildOrderConfig, ExtraItem
from archscope_domain.discovery_config import QuestionBank
from archscope_domain.discovery_rules import DiscoveryRules, Evaluation
from archscope_domain.exporters import Section

log = logging.getLogger(__name__)


def question_bank() -> QuestionBank:
    return dd.question_bank()


def discovery_rules() -> DiscoveryRules:
    return dd.discovery_rules()


def build_order_config() -> BuildOrderConfig:
    """The build-order config, which carries the checklist, rules, and
    question bank it was validated against."""
    return dd.discovery_build_order()


@dataclass(frozen=True)
class EvaluationResult:
    evaluation: Evaluation
    checklist: list[Section]
    build_order: BuildOrder


def evaluate(
    notes: dict[str, dict[str, Any]],
    *,
    client_name: str,
    project_type: str,
    done_build_items: list[str],
    extra_items: Sequence[ExtraItem] = (),
) -> EvaluationResult:
    """Everything the notes trigger: revealed follow-ups and required
    tasks, the checklist, and the build order."""
    config = dd.discovery_build_order()
    return EvaluationResult(
        evaluation=config.checklist.rules.evaluate(notes),
        checklist=config.checklist.build(notes),
        build_order=config.build(
            notes, client=client_name, project_type=project_type, done_ids=set(done_build_items), extra_items=extra_items
        ),
    )


def business_analysis_payload(notes: dict[str, dict[str, Any]], *, client_name: str, business_type: str) -> dict[str, Any]:
    return dd.build_business_analysis_input(notes, client_name=client_name, business_type=business_type)


def client_explainer_payload(modules: list[str], *, business_type: str) -> dict[str, Any]:
    return dd.build_client_explainer_input(modules, business_type=business_type)


def stream_document(client: Any, payload: dict[str, Any], *, model: str | None) -> Iterator[str]:
    """Document text chunks as the model writes them. Raises
    :class:`archscope_domain.discovery.DiscoveryError` at the end if the
    response was refused or cut off."""
    return dd.stream_document(client, payload, model=model)


def gemini_models() -> tuple[str, ...]:
    """Gemini models to draft with, most accurate first."""
    return dd.gemini_models()


def stream_document_gemini(
    client: Any, payload: dict[str, Any], *, models: Sequence[str], should_fall_back: Callable[[Exception], bool]
) -> Iterator[str]:
    """Like :func:`stream_document`, on Gemini: try ``models`` in order
    (most accurate first), moving to the next when ``should_fall_back``
    says the error is per-model (free quota used up, model not available)
    — but only before any text has streamed, so a document never mixes
    two models."""
    for i, model in enumerate(models):
        chunks = dd.stream_document_gemini(client, payload, model=model)
        try:
            first = next(chunks, None)
        except Exception as exc:
            if i < len(models) - 1 and should_fall_back(exc):
                log.warning("Gemini model %s unavailable (%s); trying %s", model, exc, models[i + 1])
                continue
            raise
        log.info("Drafting with %s", model)
        if first is not None:
            yield first
        yield from chunks
        return


def suggest_modules(business_analysis_markdown: str) -> list[str]:
    return dd.suggest_modules(business_analysis_markdown)
