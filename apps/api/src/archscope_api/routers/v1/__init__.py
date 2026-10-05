"""Version 1 of the public API, mounted at ``/api/v1``."""

from fastapi import APIRouter

from . import architecture, discovery, exports, portal, proposals

api_router = APIRouter(prefix="/api/v1")
for _module in (architecture, portal, proposals, discovery, exports):
    api_router.include_router(_module.router)

__all__ = ["api_router"]
