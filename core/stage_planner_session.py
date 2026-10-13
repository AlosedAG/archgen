"""Where an applied Deal Stage Planner lives in the Streamlit session, so
the Stage Planner page (which applies it), the Discovery Call Assistant
(build-order items) and the Architecture Generator (pipeline, properties,
workflows) agree on one record.

The record sits under a ``disc_*`` key, so the router re-saves it across
page switches and it's included in Discovery notes backups:
``{"planner": StagePlanner.to_dict(), "targets": [...], "applied_on": "YYYY-MM-DD"}``.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from archscope_domain.discovery import discovery_build_order
from archscope_domain.stage_planner import StagePlanner, StagePlannerConfig, load_stage_planner_config

APPLIED_KEY = "disc_stage_planner"

TARGET_DISCOVERY = "discovery"
TARGET_ARCHITECTURE = "architecture"
TARGET_BUILD_ORDER = "build_order"
TARGETS = {
    TARGET_DISCOVERY: "Discovery Call Assistant — Processes (pipeline stages + notes)",
    TARGET_ARCHITECTURE: "Architecture Generator — deal pipeline, deal properties, workflows",
    TARGET_BUILD_ORDER: "Build order — pipeline, properties, automations, rep tasks",
}


def planner_config() -> StagePlannerConfig:
    """The validated ``stage_planner.yaml`` (raises a DiscoveryConfigError subclass if invalid)."""
    return load_stage_planner_config(discovery_build_order())


def applied_record() -> dict[str, Any] | None:
    record = st.session_state.get(APPLIED_KEY)
    return record if isinstance(record, dict) and isinstance(record.get("planner"), dict) else None


def applied_planner(target: str) -> StagePlanner | None:
    """The applied planner, if it was applied to ``target``."""
    record = applied_record()
    if not record or target not in (record.get("targets") or []):
        return None
    return StagePlanner.from_dict(record["planner"])
