"""FastAPI dependencies and response helpers shared by every router."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, ParamSpec, TypeVar

import anthropic
from fastapi import Depends, Request, Response
from fastapi.security import APIKeyCookie, APIKeyHeader
from google import genai
from pydantic import SecretStr
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from archscope_domain.ports import PortalReader
from archscope_integrations.hubspot import HubSpotClient

from ..mail import Mailer, OutboxMailer, SmtpMailer
from ..persistence.blobs import BlobStore, LocalBlobStore
from ..persistence.db import session_scope
from ..persistence.security import SecretBox
from ..problems import ProblemError
from ..services import auth, discovery, workspace_secrets
from ..services.auth import Principal
from ..settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


# ---- Persistence & sign-in ------------------------------------------------


def get_db(settings: SettingsDep) -> Iterator[Session]:
    """A database session per request: committed on success, rolled back on error."""
    with session_scope(settings.database_url) as db:
        yield db


DbDep = Annotated[Session, Depends(get_db)]


def get_blob_store(settings: SettingsDep) -> BlobStore:
    return LocalBlobStore(settings.blob_dir)


BlobStoreDep = Annotated[BlobStore, Depends(get_blob_store)]


def get_secret_box(settings: SettingsDep) -> SecretBox:
    return SecretBox(settings.secret_key.get_secret_value() if settings.secret_key else None)


SecretBoxDep = Annotated[SecretBox, Depends(get_secret_box)]

# Development fallback for HMAC-ing email codes when no secret key is set
# (production refuses to start without one).
_DEV_PEPPER = "archscope-local-development-only"


def get_code_pepper(settings: SettingsDep) -> str:
    return settings.secret_key.get_secret_value() if settings.secret_key else _DEV_PEPPER


CodePepperDep = Annotated[str, Depends(get_code_pepper)]


def get_mailer(settings: SettingsDep) -> Mailer | None:
    """SMTP when configured; the file outbox in local/test; otherwise None (no email)."""
    if settings.smtp_enabled and settings.smtp_host and settings.smtp_password:
        return SmtpMailer(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
            sender=settings.mail_from or settings.smtp_username or "",
            security=settings.smtp_security,
        )
    if settings.is_dev:
        return OutboxMailer(settings.outbox_dir)
    return None


MailerDep = Annotated[Mailer | None, Depends(get_mailer)]

# Documented in OpenAPI as the cookie auth scheme; read manually so the
# cookie name can come from settings.
_session_cookie = APIKeyCookie(name="archscope_session", scheme_name="SessionCookie", auto_error=False)


def current_principal(
    request: Request, db: DbDep, settings: SettingsDep, _documented: Annotated[str | None, Depends(_session_cookie)] = None
) -> Principal:
    """The signed-in user, from the session cookie. 401 if there isn't one."""
    return auth.principal_for_token(db, request.cookies.get(settings.session_cookie))


PrincipalDep = Annotated[Principal, Depends(current_principal)]

_P = ParamSpec("_P")
_R = TypeVar("_R")


async def offload(fn: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs) -> _R:
    """Run blocking / CPU-bound domain work in the threadpool so the event
    loop keeps serving other requests (SSE streams, health checks)."""
    return await run_in_threadpool(fn, *args, **kwargs)


# ---- HubSpot -------------------------------------------------------------
# The workspace's encrypted stored token (set under Settings); API clients
# may instead send one per request in the X-HubSpot-Token header.

_hubspot_token = APIKeyHeader(
    name="X-HubSpot-Token",
    scheme_name="HubSpotToken",
    description="HubSpot private app access token (read-only scopes). Never stored or logged.",
    auto_error=False,
)


def get_portal_reader(
    token: Annotated[str | None, Depends(_hubspot_token)], principal: PrincipalDep, db: DbDep, box: SecretBoxDep
) -> PortalReader:
    """The workspace's stored HubSpot token (Settings), or one sent in the header by API clients."""
    token = token or workspace_secrets.reveal(db, box, principal.workspace_id, workspace_secrets.HUBSPOT_TOKEN)
    if not token:
        raise ProblemError(
            400,
            "hubspot-token-required",
            "HubSpot isn't connected",
            "Add the HubSpot private app token under Settings, or send it in the X-HubSpot-Token header.",
        )
    return HubSpotClient(token)


PortalReaderDep = Annotated[PortalReader, Depends(get_portal_reader)]


# ---- AI drafting -----------------------------------------------------------
# Gemini when a Gemini key is set (free-tier testing), else Claude. Keys come
# from the workspace's Settings page first, then the server environment.


@dataclass(frozen=True)
class AiBackend:
    provider: Literal["gemini", "anthropic"]
    client: Any
    # Gemini models to try, most accurate first (empty for Claude, whose
    # model comes from settings.anthropic_model).
    models: tuple[str, ...] = ()


def get_ai_client(settings: SettingsDep, principal: PrincipalDep, db: DbDep, box: SecretBoxDep) -> AiBackend:
    """The drafting model for this workspace: Gemini if a Gemini key is
    stored (or GEMINI_API_KEY is set), otherwise Anthropic."""

    def key_for(name: str, env: SecretStr | None) -> str | None:
        return workspace_secrets.reveal(db, box, principal.workspace_id, name) or (env.get_secret_value() if env else None)

    if gemini_key := key_for(workspace_secrets.GEMINI_KEY, settings.gemini_api_key):
        return AiBackend("gemini", genai.Client(api_key=gemini_key), discovery.gemini_models())
    if anthropic_key := key_for(workspace_secrets.ANTHROPIC_KEY, settings.anthropic_api_key):
        return AiBackend("anthropic", anthropic.Anthropic(api_key=anthropic_key))
    raise ProblemError(
        503, "ai-not-configured", "AI drafting is not configured", "Add a Gemini or Anthropic API key under Settings."
    )


AiClientDep = Annotated[AiBackend, Depends(get_ai_client)]


# ---- binary responses ----------------------------------------------------

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "png": "image/png",
    "dot": "text/vnd.graphviz; charset=utf-8",
    "drawio": "application/vnd.jgraph.mxfile",
}


def file_response(content: bytes, *, stem: str, ext: str) -> Response:
    """A download with a safe filename and the correct media type."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "document"
    return Response(
        content=content,
        media_type=MEDIA_TYPES[ext],
        headers={"Content-Disposition": f'attachment; filename="{safe}.{ext}"'},
    )


def binary_responses(*exts: str) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses=`` entry documenting a file download."""
    return {200: {"content": {MEDIA_TYPES[e]: {"schema": {"type": "string", "format": "binary"}} for e in exts}}}
