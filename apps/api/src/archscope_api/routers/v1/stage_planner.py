"""Deal Stage Planner — the pre-call template, and importing a filled-out copy for review.

Input ingestion only: parsing never writes anywhere; the client decides
what to apply after review.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Request, Response

from archscope_domain.stage_planner import StagePlanner, StagePlannerParseError

from ...problems import ProblemError
from ...schemas.stage_planner import StagePlannerImport, StagePlannerPreviewRequest
from ...services import stage_planner
from ..deps import binary_responses, file_response, offload

router = APIRouter(prefix="/stage-planner", tags=["stage planner"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get(
    "/template", response_class=Response, responses=binary_responses("xlsx"), summary="Download the blank pre-call template"
)
async def template() -> Response:
    return file_response(await offload(stage_planner.template), stem="HubSpot_Deal_Stage_Planner", ext="xlsx")


@router.post(
    "/import",
    response_model=StagePlannerImport,
    summary="Parse a filled-out planner (.xlsx request body) for review",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def import_planner(request: Request) -> StagePlannerImport:
    content = await request.body()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ProblemError(413, "file-too-large", "The planner is too large", "Upload a workbook under 5 MB.")
    try:
        result = await offload(stage_planner.parse, content)
    except StagePlannerParseError as exc:
        raise ProblemError(422, "not-a-stage-planner", "That file isn't a readable Stage Planner", str(exc)) from None
    return _response(result)


@router.post("/preview", response_model=StagePlannerImport, summary="Map reviewed / edited stages again")
async def preview(body: StagePlannerPreviewRequest) -> StagePlannerImport:
    planner = StagePlanner.from_dict(body.model_dump())
    return _response(await offload(stage_planner.preview, planner))


def _response(result: stage_planner.PlannerImport) -> StagePlannerImport:
    return StagePlannerImport.model_validate(
        {
            **asdict(result.planner),
            "discovery_answer": result.discovery_answer,
            "discovery_notes": result.discovery_notes,
            "pipeline": asdict(result.pipeline),
            "properties": [asdict(p) for p in result.properties],
            "workflows": [asdict(w) for w in result.workflows],
            "build_items": [{k: v for k, v in asdict(i).items() if k != "template"} for i in result.build_items],
        }
    )
