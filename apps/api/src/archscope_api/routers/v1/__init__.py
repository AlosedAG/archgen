"""Version 1 of the public API, mounted at ``/api/v1``. Every route here
requires a signed-in user; sign-in itself lives in ``routers.auth``."""

from fastapi import APIRouter, Depends

from ..deps import current_principal
from . import architecture, discovery, exports, feedback, portal, projects, proposals, stage_planner, workspace

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(current_principal)])
for _module in (architecture, portal, proposals, discovery, exports, stage_planner, projects, workspace, feedback):
    api_router.include_router(_module.router)

__all__ = ["api_router"]
