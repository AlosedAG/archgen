"""Generic document exports used by every module's download buttons."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response

from ...schemas.exports import MarkdownExportRequest, SectionsExportRequest
from ...services import exports
from ..deps import binary_responses, file_response, offload

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post(
    "/markdown", response_class=Response, responses=binary_responses("docx", "pdf"), summary="Markdown document to Word or PDF"
)
async def export_markdown(body: MarkdownExportRequest, format: Literal["docx", "pdf"] = Query("docx")) -> Response:
    content = await offload(exports.markdown_document, body.markdown, body.title, format)
    return file_response(content, stem=body.title or "document", ext=format)


@router.post(
    "/sections",
    response_class=Response,
    responses=binary_responses("docx", "xlsx", "csv", "pdf"),
    summary="Titled table sections to Word, Excel, CSV or PDF",
)
async def export_sections(body: SectionsExportRequest, format: Literal["docx", "xlsx", "csv", "pdf"] = Query("docx")) -> Response:
    content = await offload(exports.sections_document, body.title, body.subtitle, body.to_domain(), format)
    return file_response(content, stem=body.title or "document", ext=format)
