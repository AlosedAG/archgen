"""Module 2 — Portal Auditor (read-only).

Runs best-practice checks against a pulled ``PortalSnapshot`` (see
``archscope_domain.docgen.DocumentationGenerator.build_snapshot``), plus targeted
record-level sampling pulled through a :class:`~archscope_domain.ports.PortalReader`. Uses the same
``RulesEngine`` Module 1 uses to generate blueprints, so naming-convention
drift is checked against literally the rules the generator itself follows.

Record-level checks always sample (never pull a full portal's records) and
say so in each finding's description. A failed pull for one check (missing
scope, API error) is recorded as a Low-severity finding rather than
aborting the whole audit.
"""

from __future__ import annotations

import difflib
from itertools import combinations

from archscope_domain.models import Finding, PortalSnapshot
from archscope_domain.ports import PortalAPIError, PortalReader, PortalScopeError
from archscope_domain.rules import RulesEngine

# Well-known HubSpot standard-object type IDs, used to make custom-object
# association targets human-readable in findings.
STANDARD_TYPE_ID_LABELS = {
    "0-1": "Contact",
    "0-2": "Company",
    "0-3": "Deal",
    "0-5": "Ticket",
}


class PortalAuditor:
    def __init__(self, client: PortalReader, rules_engine: RulesEngine | None = None):
        self.client = client
        self.rules = rules_engine or RulesEngine()

    def run(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        findings += self._check_duplicate_and_near_duplicate_properties(snapshot)
        findings += self._check_naming_drift(snapshot)
        findings += self._check_workflow_risks(snapshot)
        findings += self._check_permission_anomalies(snapshot)
        findings += self._check_unused_and_required_properties(snapshot)
        findings += self._check_orphaned_records(snapshot)
        return findings

    # ---- 1. duplicate / near-duplicate properties -------------------------

    def _check_duplicate_and_near_duplicate_properties(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        threshold = self.rules.picklist_similarity_threshold()

        for schema in snapshot.object_schemas:
            seen_labels: dict[str, str] = {}
            for prop in schema.properties:
                label_key = prop.label.strip().lower()
                if label_key and label_key in seen_labels and seen_labels[label_key] != prop.name:
                    findings.append(
                        Finding(
                            area="Properties",
                            object_type=schema.label,
                            description=(
                                f"'{schema.label}' has two properties with the same label "
                                f"'{prop.label}': '{seen_labels[label_key]}' and '{prop.name}'."
                            ),
                            severity="Medium",
                            recommended_fix=(
                                "Rename or archive one of the duplicate properties to avoid "
                                "confusing report/workflow builders."
                            ),
                        )
                    )
                elif label_key:
                    seen_labels[label_key] = prop.name

                if prop.options and len(prop.options) > 1:
                    for a, b in combinations(prop.options, 2):
                        if a == b:
                            continue
                        a_norm, b_norm = a.strip().lower(), b.strip().lower()
                        ratio = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
                        if ratio >= threshold:
                            findings.append(
                                Finding(
                                    area="Properties",
                                    object_type=schema.label,
                                    description=(
                                        f"Picklist '{prop.label}' on '{schema.label}' has near-duplicate "
                                        f"options '{a}' and '{b}' ({ratio:.0%} similar)."
                                    ),
                                    severity="Low",
                                    recommended_fix=(
                                        "Merge near-duplicate picklist values and re-map existing "
                                        "records to the canonical option."
                                    ),
                                )
                            )
        return findings

    # ---- 7. naming-convention drift ---------------------------------------

    def _check_naming_drift(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []

        for schema in snapshot.object_schemas:
            if schema.is_custom:
                name_to_check = schema.singular_label or schema.label
                is_valid, message = self.rules.check_naming(name_to_check, "custom_object")
                if not is_valid:
                    findings.append(
                        Finding(
                            area="Naming",
                            object_type=schema.label,
                            description=f"Custom object naming drift: {message}",
                            severity="Low",
                            recommended_fix="Rename to match the naming convention (see Architecture Generator rules).",
                        )
                    )
            for prop in schema.properties:
                if prop.hubspot_defined:
                    continue
                is_valid, message = self.rules.check_naming(prop.name, "property")
                if not is_valid:
                    findings.append(
                        Finding(
                            area="Naming",
                            object_type=schema.label,
                            description=f"Property '{prop.name}' naming drift: {message}",
                            severity="Low",
                            recommended_fix="Rename the internal property name to snake_case (labels can stay human-readable).",
                        )
                    )

        for wf in snapshot.workflows:
            is_valid, message = self.rules.check_naming(wf.name, "workflow")
            if not is_valid:
                findings.append(
                    Finding(
                        area="Naming",
                        object_type=wf.object_type,
                        description=f"Workflow '{wf.name}' naming drift: {message}",
                        severity="Low",
                        recommended_fix="Rename to '<Object> | <Purpose>' for consistency and easier auditing later.",
                    )
                )

        for pl in snapshot.pipelines:
            is_valid, message = self.rules.check_naming(pl.label, "pipeline")
            if not is_valid:
                findings.append(
                    Finding(
                        area="Naming",
                        object_type=pl.object_type,
                        description=f"Pipeline '{pl.label}' naming drift: {message}",
                        severity="Low",
                        recommended_fix="Rename to '<Object> Pipeline' for consistency.",
                    )
                )
        return findings

    # ---- 5. workflow re-enrollment + unconditional overwrite --------------

    def _check_workflow_risks(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for wf in snapshot.workflows:
            unconditional_sets = [
                a
                for a in wf.actions
                if isinstance(a, dict) and ("SET_PROPERTY" in str(a.get("type", "")).upper() or "propertyName" in a)
            ]
            if not unconditional_sets:
                continue
            prop_names = ", ".join(sorted({str(a.get("propertyName", "?")) for a in unconditional_sets}))
            plural = "ies" if len(unconditional_sets) != 1 else "y"
            if wf.re_enrollment_enabled:
                findings.append(
                    Finding(
                        area="Workflows",
                        object_type=wf.object_type,
                        description=(
                            f"Workflow '{wf.name}' has re-enrollment enabled and sets propert{plural} "
                            f"({prop_names}) with no conditional branch found — every re-enrollment will "
                            "overwrite it again."
                        ),
                        severity="High",
                        recommended_fix=(
                            "Add an 'only if blank' / conditional branch before the SET_PROPERTY action, "
                            "or disable re-enrollment if it isn't required."
                        ),
                    )
                )
            else:
                findings.append(
                    Finding(
                        area="Workflows",
                        object_type=wf.object_type,
                        description=(
                            f"Workflow '{wf.name}' sets propert{plural} ({prop_names}) unconditionally — "
                            "this can silently clobber manually-entered or integration-sourced data."
                        ),
                        severity="Medium",
                        recommended_fix="Add an 'only if blank' / conditional branch before the SET_PROPERTY action.",
                    )
                )
        return findings

    # ---- 6. permission / team scoping anomalies ----------------------------

    def _check_permission_anomalies(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for owner in snapshot.owners:
            if not owner.teams and not owner.archived:
                findings.append(
                    Finding(
                        area="Permissions",
                        object_type="Owner",
                        description=f"Owner '{owner.first_name} {owner.last_name}' ({owner.email}) is not assigned to any team.",
                        severity="Low",
                        recommended_fix="Assign the owner to a team, or archive the user if they're no longer active.",
                    )
                )
        for team in snapshot.teams:
            if team.member_count == 0:
                findings.append(
                    Finding(
                        area="Permissions",
                        object_type="Team",
                        description=f"Team '{team.name}' has zero members.",
                        severity="Medium",
                        recommended_fix="Confirm the team is still needed; remove it if stale, or assign members if newly created.",
                    )
                )
        return findings

    # ---- 2 & 3. unused / required properties (record sampling) -----------

    def _check_unused_and_required_properties(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        sample_size = self.rules.record_sample_size()

        for schema in snapshot.object_schemas:
            if not schema.properties:
                continue
            prop_names = [p.name for p in schema.properties]
            try:
                sample = self.client.get_records_sample(schema.object_type, limit=sample_size, properties=prop_names)
            except (PortalScopeError, PortalAPIError) as exc:
                findings.append(
                    Finding(
                        area="Records",
                        object_type=schema.label,
                        description=f"Could not sample records to check for unused/missing properties: {exc}",
                        severity="Low",
                        recommended_fix="Grant record-read scope for this object and re-run the audit.",
                    )
                )
                continue
            if not sample:
                continue

            baseline = {r["name"]: r for r in self.rules.get_standard_object_baseline_properties(schema.label)}
            required_names = {name for name, rule in baseline.items() if rule.get("required")}

            for prop in prop_names:
                populated = sum(1 for r in sample if (r.get("properties") or {}).get(prop))
                if populated == 0:
                    findings.append(
                        Finding(
                            area="Records",
                            object_type=schema.label,
                            description=f"Property '{prop}' has no value set in a sample of {len(sample)} {schema.label} records.",
                            severity="Low",
                            recommended_fix="Confirm the property is still in use; archive it if dead, or check the workflow/form meant to populate it.",
                        )
                    )
                if prop in required_names and populated < len(sample):
                    missing = len(sample) - populated
                    findings.append(
                        Finding(
                            area="Records",
                            object_type=schema.label,
                            description=(
                                f"Required property '{prop}' is missing on {missing} of {len(sample)} "
                                f"sampled {schema.label} records."
                            ),
                            severity="High",
                            recommended_fix="Add a required-field validation, a form requirement, or a backfill workflow for this property.",
                        )
                    )
        return findings

    # ---- 4. orphaned / unassociated records --------------------------------

    def _check_orphaned_records(self, snapshot: PortalSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        sample_size = min(self.rules.record_sample_size(), 100)

        for schema in snapshot.object_schemas:
            if not schema.is_custom or not schema.associations:
                continue
            assoc = schema.associations[0]
            to_type_label = STANDARD_TYPE_ID_LABELS.get(assoc.to_object, assoc.to_object)
            try:
                sample = self.client.get_records_sample(schema.object_type, limit=sample_size)
            except (PortalScopeError, PortalAPIError) as exc:
                findings.append(
                    Finding(
                        area="Associations",
                        object_type=schema.label,
                        description=f"Could not sample records to check for orphans: {exc}",
                        severity="Low",
                        recommended_fix="Grant record-read scope for this object and re-run the audit.",
                    )
                )
                continue
            if not sample:
                continue
            ids = [str(r["id"]) for r in sample if r.get("id")]
            try:
                assoc_map = self.client.get_associations_sample(schema.object_type, assoc.to_object, ids)
            except (PortalScopeError, PortalAPIError) as exc:
                findings.append(
                    Finding(
                        area="Associations",
                        object_type=schema.label,
                        description=f"Could not check associations to {to_type_label}: {exc}",
                        severity="Low",
                        recommended_fix="Grant association-read scope and re-run the audit.",
                    )
                )
                continue
            orphaned = [oid for oid in ids if not assoc_map.get(oid)]
            if orphaned:
                findings.append(
                    Finding(
                        area="Associations",
                        object_type=schema.label,
                        description=(
                            f"{len(orphaned)} of {len(ids)} sampled {schema.label} records have no association "
                            f"to {to_type_label} (expected via '{assoc.label}')."
                        ),
                        severity="Medium",
                        recommended_fix=f"Backfill the missing {to_type_label} association, or confirm these records are intentionally standalone.",
                    )
                )
        return findings


# ---- exporters -------------------------------------------------------------


def findings_to_markdown(findings: list[Finding]) -> str:
    lines = ["# Portal Audit Findings", ""]
    if not findings:
        lines.append("No findings.")
        return "\n".join(lines)
    lines.append("| Severity | Area | Object | Description | Recommended Fix |")
    lines.append("|---|---|---|---|---|")
    for f in sorted(findings, key=lambda f: {"High": 0, "Medium": 1, "Low": 2}.get(f.severity, 3)):
        lines.append(f"| {f.severity} | {f.area} | {f.object_type} | {f.description} | {f.recommended_fix} |")
    return "\n".join(lines)


def findings_to_csv(findings: list[Finding]) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Severity", "Area", "Object", "Description", "Recommended Fix"])
    for f in sorted(findings, key=lambda f: {"High": 0, "Medium": 1, "Low": 2}.get(f.severity, 3)):
        writer.writerow([f.severity, f.area, f.object_type, f.description, f.recommended_fix])
    return buffer.getvalue()
