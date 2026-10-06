"""Liveness/readiness probes (unversioned, for orchestrators)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter

from ..schemas.common import Health
from .deps import SettingsDep, offload

router = APIRouter(tags=["health"])


def _version() -> str:
    try:
        return version("archscope-api")
    except PackageNotFoundError:  # pragma: no cover - source checkout without install
        return "0.0.0+local"


@router.get("/healthz", response_model=Health, summary="Liveness probe")
async def healthz(settings: SettingsDep) -> Health:
    return Health(status="ok", version=_version(), environment=settings.environment)


@router.get("/readyz", response_model=Health, summary="Readiness probe")
async def readyz(settings: SettingsDep) -> Health:
    """Ready once the domain's configuration loads. Phase 2 adds database
    and Redis checks here."""
    from ..services import architecture, discovery

    await offload(architecture.rules_engine)
    await offload(discovery.question_bank)
    return Health(status="ok", version=_version(), environment=settings.environment)
