"""RulesEngine — single source of truth for HubSpot best-practice rules.

Loads rules/rules.yaml once and exposes small, pure lookup/check methods.
Used by core.blueprint (Module 1) to generate compliant, risk-flagged
suggestions, and by core.audit (Module 2) to check a live portal against
the exact same rules — so "naming-convention drift" is checked against
literally the rules the generator itself follows.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

_RULES_PATH = Path(__file__).parent / "rules.yaml"

_PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _looks_plural(name: str) -> bool:
    lowered = name.lower()
    if lowered.endswith("ies") and len(lowered) > 3:
        return True
    if lowered.endswith("ss") or lowered.endswith("us"):
        return False
    return lowered.endswith("s")


class RulesEngine:
    def __init__(self, rules_path: Optional[Path] = None):
        path = rules_path or _RULES_PATH
        with open(path, "r", encoding="utf-8") as f:
            self._rules: dict[str, Any] = yaml.safe_load(f) or {}

    # ---- raw lookups ---------------------------------------------------

    def get_naming_conventions(self) -> dict:
        return self._rules.get("naming_conventions", {})

    def get_base_currency_rule(self) -> dict:
        return self._rules.get("base_currency", {})

    def get_standard_object_baseline_properties(self, object_type: str) -> list[dict]:
        return self._rules.get("standard_object_baseline_properties", {}).get(object_type, [])

    def get_pipeline_template(self, object_type: str) -> list[dict]:
        templates = self._rules.get("pipeline_templates", {})
        return templates.get(object_type) or templates.get("generic_custom", [])

    def get_integration_heuristics(self, integration_key: str) -> dict:
        heuristics = self._rules.get("integration_heuristics", {})
        return heuristics.get(integration_key) or heuristics.get("other", {})

    def get_object_model_keywords(self) -> dict:
        return self._rules.get("object_model_keywords", {})

    def get_audit_thresholds(self) -> dict:
        return self._rules.get("audit_thresholds", {})

    # ---- checks ----------------------------------------------------------

    def check_naming(self, name: str, kind: str) -> tuple[bool, str]:
        """Validate `name` against the convention for `kind`.

        kind: "custom_object" | "property" | "workflow" | "pipeline"
        Returns (is_valid, message); message is empty when valid.
        """
        if kind == "custom_object":
            if not _PASCAL_CASE_RE.match(name):
                return False, f"'{name}' should be singular PascalCase (e.g. 'Membership')."
            if _looks_plural(name):
                return False, f"'{name}' looks plural; custom object names should be singular."
            return True, ""
        if kind == "property":
            if not _SNAKE_CASE_RE.match(name):
                return False, f"'{name}' should be snake_case (e.g. 'membership_status')."
            return True, ""
        if kind == "workflow":
            if "|" not in name:
                return False, f"'{name}' should follow the '<Object> | <Purpose>' naming pattern."
            return True, ""
        if kind == "pipeline":
            if not name.endswith("Pipeline"):
                return False, f"'{name}' should follow the '<Object> Pipeline' naming pattern."
            return True, ""
        raise ValueError(f"Unknown naming kind: {kind}")

    def is_overwrite_risk(self, action_summary: str) -> tuple[bool, str]:
        """Heuristically flag a workflow action summary as an overwrite risk."""
        risk_cfg = self._rules.get("overwrite_risk", {})
        action_keywords = [k.lower() for k in risk_cfg.get("action_keywords", [])]
        safe_qualifiers = [k.lower() for k in risk_cfg.get("safe_qualifiers", [])]
        lowered = action_summary.lower()
        has_action = any(kw in lowered for kw in action_keywords)
        is_safe = any(q in lowered for q in safe_qualifiers)
        if has_action and not is_safe:
            return True, "Sets/updates a property unconditionally — add an 'only if blank' or conditional branch."
        return False, ""

    def picklist_similarity_threshold(self) -> float:
        return float(self.get_audit_thresholds().get("picklist_similarity_threshold", 0.85))

    def record_sample_size(self) -> int:
        return int(self.get_audit_thresholds().get("record_sample_size", 100))
