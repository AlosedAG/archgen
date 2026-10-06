"""ASGI entry point: ``uvicorn archscope_api.main:app``.

:func:`create_app` is a factory so tests (and future workers) build an
isolated app with their own settings and dependency overrides.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .problems import install_problem_handlers
from .routers import health
from .routers.v1 import api_router
from .settings import Settings, get_settings

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware:
    """Propagates (or assigns) a request id: available as
    ``request.state.request_id``, echoed in the response header, and
    included in every problem response as ``trace_id``. Pure ASGI, so it
    doesn't buffer streaming (SSE) responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.lower().encode())
        request_id = incoming.decode()[:128] if incoming else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((REQUEST_ID_HEADER.encode(), request_id.encode()))
            await send(message)

        await self.app(scope, receive, send_with_id)


def _operation_id(route: APIRoute) -> str:
    """Stable, readable operation ids -> clean generated client method
    names (e.g. ``architecture_generate_blueprint``)."""
    return f"{route.tags[0]}_{route.name}" if route.tags else route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    app = FastAPI(
        title="ArchitectureScope API",
        version="0.4.0",
        summary="HubSpot implementation toolkit for solutions architects. Read-only against HubSpot.",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        generate_unique_id_function=_operation_id,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-HubSpot-Token", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Content-Disposition"],
    )
    app.add_middleware(RequestIdMiddleware)
    install_problem_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router)
    return app


app = create_app()
