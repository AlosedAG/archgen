"""Generic document export contract (shared by Modules 5-11)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import ApiModel

MarkdownFormat = Literal["docx", "pdf"]
SectionsFormat = Literal["docx", "xlsx", "csv", "pdf"]


class MarkdownExportRequest(ApiModel):
    markdown: str = Field(max_length=500_000, description="Headings (#/##/###), '-' bullets and **bold** are rendered.")
    title: str = Field("", max_length=300)


class ExportSection(ApiModel):
    title: str = Field(max_length=300)
    rows: list[dict[str, str]] = Field(default_factory=list, description="Table rows; columns come from the first row's keys.")


class SectionsExportRequest(ApiModel):
    title: str = Field(max_length=300)
    subtitle: str = Field("", max_length=1_000)
    sections: list[ExportSection] = Field(default_factory=list)

    def to_domain(self) -> list[tuple[str, list[dict[str, str]]]]:
        return [(s.title, s.rows) for s in self.sections]
