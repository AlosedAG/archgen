"""RFC 9457 "Problem Details for HTTP APIs" — every error this API returns
is ``application/problem+json`` with a stable ``type`` URI clients can
switch on, a human ``title``/``detail``, and the request's ``trace_id``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from archscope_domain.discovery_config import DiscoveryConfigError
from archscope_domain.ports import PortalAPIError, PortalScopeError

log = logging.getLogger("archscope_api")

PROBLEM_JSON = "application/problem+json"
TYPE_BASE = "https://architecturescope.dev/problems/"


class ProblemError(Exception):
    """Raise from any layer above the domain to return a problem response."""

    def __init__(self, status: int, slug: str, title: str, detail: str = "", **extra: Any):
        super().__init__(detail or title)
        self.status, self.slug, self.title, self.detail, self.extra = status, slug, title, detail, extra


def problem_response(request: Request, status: int, slug: str, title: str, detail: str = "", **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": TYPE_BASE + slug,
        "title": title,
        "status": status,
        "detail": detail or title,
        "instance": request.url.path,
        "trace_id": getattr(request.state, "request_id", None),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(request, exc.status, exc.slug, exc.title, exc.detail, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
        return problem_response(
            request, 422, "validation-error", "Request validation failed", f"{len(errors)} invalid field(s).", errors=errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        slug = {404: "not-found", 405: "method-not-allowed"}.get(exc.status_code, "http-error")
        return problem_response(request, exc.status_code, slug, str(exc.detail))

    @app.exception_handler(PortalScopeError)
    async def _portal_scope(request: Request, exc: PortalScopeError) -> JSONResponse:
        return problem_response(request, 502, "hubspot-access-denied", "HubSpot rejected the token", str(exc))

    @app.exception_handler(PortalAPIError)
    async def _portal_api(request: Request, exc: PortalAPIError) -> JSONResponse:
        return problem_response(request, 502, "hubspot-unavailable", "HubSpot request failed", str(exc))

    @app.exception_handler(DiscoveryConfigError)
    async def _discovery_config(request: Request, exc: DiscoveryConfigError) -> JSONResponse:
        log.error("discovery question bank invalid: %s", exc.problems)
        return problem_response(
            request, 500, "discovery-config-invalid", "Discovery question bank is invalid", problems=exc.problems
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return problem_response(request, 500, "internal-error", "Internal server error")
