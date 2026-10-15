"""Discovery Call Assistant use cases (Module 11)."""

from __future__ import annotations

import logging
import time
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


def business_analysis_payload(
    notes: dict[str, dict[str, Any]], *, client_name: str, business_type: str, client_website: str = "", website_excerpt: str = ""
) -> dict[str, Any]:
    return dd.build_business_analysis_input(
        notes,
        client_name=client_name,
        business_type=business_type,
        client_website=client_website,
        website_excerpt=website_excerpt,
    )


def with_website(payload: dict[str, Any], read: Callable[[str], str]) -> Iterator[DraftStatus]:
    """Fill the payload's website excerpt by reading the client's homepage
    (``read`` returns the excerpt or raises), reporting progress. A site
    that can't be read leaves a note instead of failing the draft."""
    client = payload.get("client", {})
    url = client.get("website", "")
    if not url:
        return
    yield DraftStatus("Reading the client's website…")
    try:
        client["website_excerpt"] = read(url)
        yield DraftStatus("Read the client's website")
    except Exception as exc:
        log.info("Couldn't read %s: %s", url, exc)
        client["website_excerpt"] = f"(The website couldn't be read: {exc})"
        yield DraftStatus("Couldn't read the client's website — continuing without it")


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


@dataclass(frozen=True)
class DraftStatus:
    """A progress note sent alongside the streamed text (which model is
    drafting, or that one was busy and another is being tried)."""

    message: str
    model: str = ""


# How a failed Gemini call is handled before any text has streamed:
# "retry" = a temporary overload (503/500/504): wait and try the same model
# again, then move on; "next" = this model can't be used now (quota used
# up, not available to the key): move straight to the next model.
RETRY, NEXT = "retry", "next"
RETRY_DELAYS = (3.0,)


def ordered_models(models: Sequence[str], preferred: str | None) -> tuple[str, ...]:
    """``models`` with ``preferred`` (one of them) moved to the front."""
    if not preferred:
        return tuple(models)
    return (preferred, *(m for m in models if m != preferred))


def model_note(model: str) -> str:
    return dd.GEMINI_MODEL_NOTES.get(model, "")


def model_label(model: str) -> str:
    """ "gemini-3.8-flash" -> "Gemini 3.8 Flash"."""
    return " ".join(part.capitalize() if not part[0].isdigit() else part for part in model.split("-"))


def stream_document_gemini(
    client: Any,
    payload: dict[str, Any],
    *,
    models: Sequence[str],
    classify: Callable[[Exception], str | None],
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str | DraftStatus]:
    """Like :func:`stream_document`, on Gemini: try ``models`` in order
    (most accurate first). A temporarily overloaded model is retried after
    a short pause, then the next model is used; a model whose quota is used
    up is skipped at once. Switching only happens before any text has
    streamed, so a document never mixes two models. Yields
    :class:`DraftStatus` notes between the text chunks."""
    for i, model in enumerate(models):
        has_next = i < len(models) - 1
        for attempt in range(len(RETRY_DELAYS) + 1):
            again = " (second try)" if attempt else ""
            yield DraftStatus(f"Drafting with {model_label(model)}{again}", model)
            chunks = dd.stream_document_gemini(client, payload, model=model)
            try:
                first = next(chunks, None)
            except Exception as exc:
                kind = classify(exc)
                if kind == RETRY and attempt < len(RETRY_DELAYS):
                    delay = RETRY_DELAYS[attempt]
                    log.warning("Gemini model %s is busy (%s); retrying in %.0fs", model, exc, delay)
                    yield DraftStatus(f"{model_label(model)} is busy — trying again in a few seconds…", model)
                    sleep(delay)
                    continue
                if kind in (RETRY, NEXT) and has_next:
                    log.warning("Gemini model %s unavailable (%s); trying %s", model, exc, models[i + 1])
                    reason = "is busy" if kind == RETRY else "can't be used right now"
                    yield DraftStatus(
                        f"{model_label(model)} {reason} — switching to {model_label(models[i + 1])}…", models[i + 1]
                    )
                    break
                raise
            log.info("Drafting with %s", model)
            if first is not None:
                yield first
            yield from chunks
            return


def suggest_modules(business_analysis_markdown: str) -> list[str]:
    return dd.suggest_modules(business_analysis_markdown)
