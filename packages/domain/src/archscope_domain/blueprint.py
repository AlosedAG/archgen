"""Module 1 — Architecture Generator: blueprint generation from project inputs.

Applies the best-practice heuristics defined in config/rules.yaml (via
RulesEngine) to a BlueprintInput and produces a Blueprint: recommended
custom objects, a property data dictionary, an association model,
pipeline/stage definitions, a naming convention summary, and a suggested
workflow list with overwrite-risk flags.
"""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import UTC, datetime
from typing import Any

from archscope_domain.models import (
    AssociationDef,
    Blueprint,
    BlueprintInput,
    CustomObjectDef,
    PipelineDef,
    PropertyDef,
    StageDef,
    WorkflowSuggestion,
)
from archscope_domain.rules import RulesEngine

_INTEGRATION_KEY_MAP = {
    "MyStudio": "MyStudio",
    "Sakari": "Sakari",
    "Payments Provider": "payments_provider",
    "Other": "other",
}


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "integration"


def _property_from_rule(rule: dict[str, Any]) -> PropertyDef:
    return PropertyDef(
        name=rule["name"],
        label=rule["label"],
        type=rule.get("type", "string"),
        field_type=rule.get("field_type", "text"),
        group=rule.get("group", "custom_properties"),
        description=rule.get("description", ""),
        options=rule.get("options"),
        required=rule.get("required", False),
    )


class BlueprintGenerator:
    def __init__(self, rules_engine: RulesEngine):
        self.rules = rules_engine

    def generate(self, bp_input: BlueprintInput) -> Blueprint:
        warnings: list[str] = []

        standard_object_properties = self._build_standard_object_properties(bp_input)
        custom_objects = self._build_custom_objects(bp_input, warnings)
        self._apply_integration_heuristics(bp_input, standard_object_properties, warnings)
        associations = self._build_associations(custom_objects)
        pipelines = self._build_pipelines(bp_input, warnings)
        base_currency_note = self._resolve_base_currency(bp_input, warnings)
        workflows = self._build_workflows(bp_input, custom_objects)

        if bp_input.custom_object_notes.strip():
            warnings.append(
                "Custom object notes provided but not auto-modeled — review manually: "
                f"\"{bp_input.custom_object_notes.strip()}\""
            )

        return Blueprint(
            project_name=bp_input.project_name,
            generated_at=datetime.now(UTC).isoformat(),
            inputs=bp_input,
            custom_objects=custom_objects,
            standard_object_properties=standard_object_properties,
            associations=associations,
            pipelines=pipelines,
            naming_conventions=self.rules.get_naming_conventions(),
            base_currency_note=base_currency_note,
            workflows=workflows,
            warnings=warnings,
        )

    # ---- section builders ----------------------------------------------

    def _build_standard_object_properties(self, bp_input: BlueprintInput) -> dict[str, list[PropertyDef]]:
        result: dict[str, list[PropertyDef]] = {}
        for obj in bp_input.standard_objects:
            baseline = self.rules.get_standard_object_baseline_properties(obj)
            result[obj] = [_property_from_rule(r) for r in baseline]
        return result

    def _build_custom_objects(self, bp_input: BlueprintInput, warnings: list[str]) -> list[CustomObjectDef]:
        keywords = self.rules.get_object_model_keywords()
        objects: list[CustomObjectDef] = []
        for keyword in bp_input.custom_object_keywords:
            template = keywords.get(keyword) or keywords.get(keyword.lower())
            if not template:
                warnings.append(f"No template found for custom object keyword '{keyword}' — skipped.")
                continue
            name = template["object_name"]
            is_valid, message = self.rules.check_naming(name, "custom_object")
            if not is_valid:
                warnings.append(f"Custom object '{name}': {message}")
            objects.append(
                CustomObjectDef(
                    name=name,
                    plural_label=template.get("plural_label", f"{name}s"),
                    description=template.get("description", ""),
                    properties=[_property_from_rule(r) for r in template.get("properties", [])],
                )
            )
        return objects

    def _apply_integration_heuristics(
        self,
        bp_input: BlueprintInput,
        standard_object_properties: dict[str, list[PropertyDef]],
        warnings: list[str],
    ) -> None:
        for integration in bp_input.integrations:
            key = _INTEGRATION_KEY_MAP.get(integration, "other")
            heuristics = self.rules.get_integration_heuristics(key)
            for rule in heuristics.get("properties", []):
                obj = rule["object"]
                resolved = dict(rule)
                resolved["name"] = rule["name"].replace("{integration}", _slug(integration))
                resolved["label"] = rule["label"].replace("{Integration}", integration)
                prop = _property_from_rule(resolved)
                is_valid, message = self.rules.check_naming(prop.name, "property")
                if not is_valid:
                    warnings.append(f"Property '{prop.name}' ({obj}): {message}")
                existing = standard_object_properties.setdefault(obj, [])
                if not any(p.name == prop.name for p in existing):
                    existing.append(prop)

    def _build_associations(self, custom_objects: list[CustomObjectDef]) -> list[AssociationDef]:
        keywords = self.rules.get_object_model_keywords()
        templates_by_object_name = {t.get("object_name"): t for t in keywords.values()}
        associations: list[AssociationDef] = []
        for co in custom_objects:
            template = templates_by_object_name.get(co.name)
            if not template:
                continue
            for assoc in template.get("associations", []):
                associations.append(
                    AssociationDef(
                        from_object=co.name,
                        to_object=assoc["to_object"],
                        label=assoc.get("label", f"{co.name} to {assoc['to_object']}"),
                        cardinality=assoc.get("cardinality", "many-to-many"),
                    )
                )
        return associations

    def _build_pipelines(self, bp_input: BlueprintInput, warnings: list[str]) -> list[PipelineDef]:
        pipelines: list[PipelineDef] = []
        for object_type in bp_input.pipelines_required:
            template = self.rules.get_pipeline_template(object_type)
            name = f"{object_type} Pipeline"
            is_valid, message = self.rules.check_naming(name, "pipeline")
            if not is_valid:
                warnings.append(f"Pipeline '{name}': {message}")
            stages = [
                StageDef(
                    name=s["name"],
                    order=s["order"],
                    is_closed=s.get("is_closed", False),
                    is_won=s.get("is_won", False),
                )
                for s in template
            ]
            pipelines.append(PipelineDef(object_type=object_type, name=name, stages=stages))
        return pipelines

    def _resolve_base_currency(self, bp_input: BlueprintInput, warnings: list[str]) -> str:
        if not bp_input.currencies:
            return ""
        rule = self.rules.get_base_currency_rule()
        base = bp_input.currencies[0]
        note = f"Base currency: {base}. {rule.get('note', '')}".strip()
        if len(bp_input.currencies) > 1:
            warnings.append(
                f"Multiple currencies in scope ({', '.join(bp_input.currencies)}); defaulted base currency "
                f"to '{base}' — confirm with finance/ops before build."
            )
        return note

    def _build_workflows(
        self, bp_input: BlueprintInput, custom_objects: list[CustomObjectDef]
    ) -> list[WorkflowSuggestion]:
        workflows: list[WorkflowSuggestion] = []

        for integration in bp_input.integrations:
            key = _INTEGRATION_KEY_MAP.get(integration, "other")
            heuristics = self.rules.get_integration_heuristics(key)
            for rule in heuristics.get("workflows", []):
                name = rule["name"].replace("{Integration}", integration)
                is_risk, reason = self.rules.is_overwrite_risk(rule["action_summary"])
                workflows.append(
                    WorkflowSuggestion(
                        name=name,
                        object_type=rule.get("object_type", "Contact"),
                        trigger=rule.get("trigger", ""),
                        action_summary=rule["action_summary"],
                        overwrite_risk=is_risk,
                        risk_reason=reason,
                    )
                )

        for co in custom_objects:
            action = f"Notify record owner when {_slug(co.name)}_status changes"
            is_risk, reason = self.rules.is_overwrite_risk(action)
            workflows.append(
                WorkflowSuggestion(
                    name=f"{co.name} | Notify Owner on Status Change",
                    object_type=co.name,
                    trigger=f"{co.name} status property changes",
                    action_summary=action,
                    overwrite_risk=is_risk,
                    risk_reason=reason,
                )
            )

        if "Contact" in bp_input.standard_objects and (
            "Deal" in bp_input.standard_objects or "Deal" in bp_input.pipelines_required
        ):
            risky_action = "Set lifecyclestage to Customer"
            is_risk, reason = self.rules.is_overwrite_risk(risky_action)
            workflows.append(
                WorkflowSuggestion(
                    name="Contact | Set Lifecycle Stage to Customer",
                    object_type="Contact",
                    trigger="Associated Deal enters Closed Won stage",
                    action_summary=risky_action,
                    overwrite_risk=is_risk,
                    risk_reason=reason,
                )
            )
            safe_action = "Set lead source only if blank"
            is_risk_safe, reason_safe = self.rules.is_overwrite_risk(safe_action)
            workflows.append(
                WorkflowSuggestion(
                    name="Contact | Set Lead Source (Only If Blank)",
                    object_type="Contact",
                    trigger="Contact created",
                    action_summary=safe_action,
                    overwrite_risk=is_risk_safe,
                    risk_reason=reason_safe,
                )
            )

        return workflows


def blueprint_to_json(blueprint: Blueprint) -> str:
    return json.dumps(dataclasses.asdict(blueprint), indent=2, default=str)


def blueprint_to_markdown(blueprint: Blueprint) -> str:
    lines: list[str] = []
    lines.append(f"# Architecture Blueprint: {blueprint.project_name}")
    lines.append("")
    lines.append(f"_Generated at {blueprint.generated_at}_")
    lines.append("")

    if blueprint.warnings:
        lines.append("## Warnings")
        for w in blueprint.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Custom Objects")
    if blueprint.custom_objects:
        lines.append("| Name | Plural Label | Description |")
        lines.append("|---|---|---|")
        for o in blueprint.custom_objects:
            lines.append(f"| {o.name} | {o.plural_label} | {o.description} |")
    else:
        lines.append("None suggested.")
    lines.append("")

    lines.append("## Data Dictionary")
    lines.append("| Object | Property | Label | Type | Required | Options | Description |")
    lines.append("|---|---|---|---|---|---|---|")
    for obj_name, props in blueprint.standard_object_properties.items():
        for p in props:
            lines.append(
                f"| {obj_name} | {p.name} | {p.label} | {p.type} | {p.required} | "
                f"{', '.join(p.options or [])} | {p.description} |"
            )
    for co in blueprint.custom_objects:
        for p in co.properties:
            lines.append(
                f"| {co.name} | {p.name} | {p.label} | {p.type} | {p.required} | "
                f"{', '.join(p.options or [])} | {p.description} |"
            )
    lines.append("")

    lines.append("## Association Model")
    lines.append("| From | To | Label | Cardinality |")
    lines.append("|---|---|---|---|")
    for a in blueprint.associations:
        lines.append(f"| {a.from_object} | {a.to_object} | {a.label} | {a.cardinality} |")
    lines.append("")

    lines.append("## Pipelines & Stages")
    for pl in blueprint.pipelines:
        lines.append(f"### {pl.name} ({pl.object_type})")
        lines.append("| Order | Stage | Closed | Won |")
        lines.append("|---|---|---|---|")
        for s in sorted(pl.stages, key=lambda stage: stage.order):
            lines.append(f"| {s.order} | {s.name} | {s.is_closed} | {s.is_won} |")
        lines.append("")

    lines.append("## Naming Conventions")
    for k, v in blueprint.naming_conventions.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## Base Currency")
    lines.append(blueprint.base_currency_note or "No currencies specified.")
    lines.append("")

    lines.append("## Suggested Workflows")
    lines.append("| Name | Object | Trigger | Action | Overwrite Risk | Risk Reason |")
    lines.append("|---|---|---|---|---|---|")
    for wf in blueprint.workflows:
        risk_flag = "**YES**" if wf.overwrite_risk else "No"
        lines.append(
            f"| {wf.name} | {wf.object_type} | {wf.trigger} | {wf.action_summary} | {risk_flag} | {wf.risk_reason} |"
        )
    lines.append("")

    return "\n".join(lines)
