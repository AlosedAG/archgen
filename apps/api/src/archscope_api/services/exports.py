"""Generic document rendering shared by every module."""

from __future__ import annotations

from typing import Literal

from archscope_domain import exporters as ex

Sections = list[tuple[str, list[dict[str, str]]]]


def markdown_document(markdown: str, title: str, fmt: Literal["docx", "pdf"]) -> bytes:
    if fmt == "docx":
        return ex.markdown_to_docx(markdown, title=title).getvalue()
    return ex.markdown_to_pdf(markdown, title=title)


def sections_document(title: str, subtitle: str, sections: Sections, fmt: Literal["docx", "xlsx", "csv", "pdf"]) -> bytes:
    if fmt == "docx":
        return ex.sections_to_docx(title, subtitle, sections).getvalue()
    if fmt == "xlsx":
        return ex.sections_to_xlsx(sections)
    if fmt == "csv":
        return ex.sections_to_csv(sections).encode("utf-8")
    return ex.sections_to_pdf(title, subtitle, sections)
