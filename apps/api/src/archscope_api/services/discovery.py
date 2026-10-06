"""Discovery Call Assistant use cases (Module 11)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from archscope_domain import discovery as dd
from archscope_domain.discovery_config import QuestionBank


def question_bank() -> QuestionBank:
    return dd.question_bank()


def business_analysis_payload(notes: dict[str, dict[str, Any]], *, client_name: str, business_type: str) -> dict[str, Any]:
    return dd.build_business_analysis_input(notes, client_name=client_name, business_type=business_type)


def client_explainer_payload(modules: list[str], *, business_type: str) -> dict[str, Any]:
    return dd.build_client_explainer_input(modules, business_type=business_type)


def stream_document(client: Any, payload: dict[str, Any], *, model: str | None) -> Iterator[str]:
    """Document text chunks as the model writes them. Raises
    :class:`archscope_domain.discovery.DiscoveryError` at the end if the
    response was refused or cut off."""
    return dd.stream_document(client, payload, model=model)


def suggest_modules(business_analysis_markdown: str) -> list[str]:
    return dd.suggest_modules(business_analysis_markdown)
