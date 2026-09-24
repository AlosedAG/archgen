"""Module 3 — Documentation Generator (read-only).

Pulls a live portal snapshot via ``core.hubspot_client.HubSpotClient`` and
builds a documentation pack: a data dictionary (object -> properties, types,
options), a workflow inventory, an association map, a pipeline/stage list,
and a roles/permissions summary. Exports as Markdown and as a styled .docx
via python-docx.

``build_snapshot`` never raises on a missing scope or a failed pull for one
data set — it records the problem in ``PortalSnapshot.warnings`` and
continues with whatever it could fetch, so one missing scope doesn't blank
out the whole documentation pack.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from core.hubspot_client import STANDARD_OBJECT_TYPES, HubSpotAPIError, HubSpotClient, HubSpotScopeError
from core.models import (
    ObjectSchema,
    Owner,
    PortalPipeline,
    PortalPipelineStage,
    PortalPropertyDef,
    PortalSnapshot,
    PortalWorkflow,
    Team,
)


def _property_from_api(p: dict) -> PortalPropertyDef:
    options = [o.get("label") or o.get("value", "") for o in (p.get("options") or [])]
    return PortalPropertyDef(
        name=p.get("name", ""),
        label=p.get("label", ""),
        type=p.get("type", ""),
        field_type=p.get("field_type", ""),
        group_name=p.get("group_name", ""),
        options=options,
        description=p.get("description", "") or "",
        hubspot_defined=bool(p.get("hubspot_defined", False)),
    )


class DocumentationGenerator:
    def __init__(self, client: HubSpotClient):
        self.client = client

    def build_snapshot(self) -> PortalSnapshot:
        warnings: list[str] = []
        object_schemas = self._pull_object_schemas(warnings)
        pipelines = self._pull_pipelines(object_schemas, warnings)
        workflows = self._pull_workflows(warnings)
        owners = self._pull_owners(warnings)
        teams = self._pull_teams(warnings)

        return PortalSnapshot(
            pulled_at=datetime.now(timezone.utc).isoformat(),
            object_schemas=object_schemas,
            pipelines=pipelines,
            workflows=workflows,
            owners=owners,
            teams=teams,
            warnings=warnings,
        )

    # ---- section pulls ----------------------------------------------------

    def _pull_object_schemas(self, warnings: list[str]) -> list[ObjectSchema]:
        schemas: list[ObjectSchema] = []

        for object_type, label in STANDARD_OBJECT_TYPES:
            try:
                props = self.client.get_properties(object_type)
            except (HubSpotScopeError, HubSpotAPIError) as exc:
                warnings.append(f"{label} properties: {exc}")
                props = []
            schemas.append(
                ObjectSchema(
                    object_type=object_type,
                    label=label,
                    is_custom=False,
                    properties=[_property_from_api(p) for p in props],
                    associations=[],
                )
            )

        try:
            custom_schemas = self.client.get_custom_object_schemas()
        except (HubSpotScopeError, HubSpotAPIError) as exc:
            warnings.append(f"Custom object schemas: {exc}")
            custom_schemas = []

        for schema in custom_schemas:
            object_type = schema.get("object_type_id") or schema.get("fully_qualified_name") or schema.get("name")
            labels = schema.get("labels") or {}
            label = labels.get("plural") or schema.get("name", object_type)
            singular_label = labels.get("singular") or schema.get("name", object_type)
            try:
                props = self.client.get_properties(object_type)
            except (HubSpotScopeError, HubSpotAPIError) as exc:
                warnings.append(f"{label} properties: {exc}")
                props = []
            from core.models import AssociationDef

            associations = [
                AssociationDef(
                    from_object=schema.get("name", object_type),
                    to_object=a.get("to_object_type_id", ""),
                    label=a.get("name", ""),
                    cardinality="",
                )
                for a in (schema.get("associations") or [])
            ]
            schemas.append(
                ObjectSchema(
                    object_type=object_type,
                    label=label,
                    is_custom=True,
                    singular_label=singular_label,
                    properties=[_property_from_api(p) for p in props],
                    associations=associations,
                )
            )

        return schemas

    def _pull_pipelines(self, object_schemas: list[ObjectSchema], warnings: list[str]) -> list[PortalPipeline]:
        pipelines: list[PortalPipeline] = []
        pipeline_eligible = [("deals", "Deal"), ("tickets", "Ticket")] + [
            (s.object_type, s.label) for s in object_schemas if s.is_custom
        ]
        for object_type, label in pipeline_eligible:
            try:
                raw_pipelines = self.client.get_pipelines(object_type)
            except (HubSpotScopeError, HubSpotAPIError) as exc:
                warnings.append(f"{label} pipelines: {exc}")
                raw_pipelines = []
            for p in raw_pipelines:
                stages = [
                    PortalPipelineStage(
                        stage_id=s.get("id", ""),
                        label=s.get("label", ""),
                        display_order=s.get("display_order", 0),
                    )
                    for s in sorted(p.get("stages", []), key=lambda s: s.get("display_order", 0))
                ]
                pipelines.append(
                    PortalPipeline(object_type=label, pipeline_id=p.get("id", ""), label=p.get("label", ""), stages=stages)
                )
        return pipelines

    def _pull_workflows(self, warnings: list[str]) -> list[PortalWorkflow]:
        workflows: list[PortalWorkflow] = []
        try:
            wf_list = self.client.get_workflows()
        except (HubSpotScopeError, HubSpotAPIError) as exc:
            warnings.append(f"Workflows: {exc}")
            return workflows

        for wf in wf_list:
            wf_id = wf.get("id")
            detail = wf
            try:
                if wf_id is not None:
                    detail = self.client.get_workflow_detail(wf_id)
            except (HubSpotScopeError, HubSpotAPIError) as exc:
                warnings.append(f"Workflow '{wf.get('name', wf_id)}' detail: {exc}")
            workflows.append(
                PortalWorkflow(
                    workflow_id=str(wf_id),
                    name=detail.get("name", wf.get("name", "")),
                    enabled=detail.get("enabled", wf.get("enabled", False)),
                    object_type=detail.get("type", wf.get("type", "")),
                    re_enrollment_enabled=bool(
                        detail.get("reEnrollmentTriggersEnabled") or wf.get("reEnrollmentTriggersEnabled")
                    ),
                    actions=detail.get("actions", []),
                )
            )
        return workflows

    def _pull_owners(self, warnings: list[str]) -> list[Owner]:
        try:
            raw_owners = self.client.get_owners()
        except (HubSpotScopeError, HubSpotAPIError) as exc:
            warnings.append(f"Owners: {exc}")
            return []
        return [
            Owner(
                owner_id=str(o.get("id", "")),
                email=o.get("email", ""),
                first_name=o.get("first_name", ""),
                last_name=o.get("last_name", ""),
                teams=[t.get("name", "") for t in (o.get("teams") or [])],
                archived=bool(o.get("archived", False)),
            )
            for o in raw_owners
        ]

    def _pull_teams(self, warnings: list[str]) -> list[Team]:
        try:
            raw_teams = self.client.get_teams()
        except (HubSpotScopeError, HubSpotAPIError) as exc:
            warnings.append(f"Teams: {exc}")
            return []
        teams = []
        for t in raw_teams:
            members = t.get("membership") or t.get("userIds") or t.get("members") or []
            teams.append(Team(team_id=str(t.get("id", "")), name=t.get("name", ""), member_count=len(members)))
        return teams


# ---- exporters -------------------------------------------------------------


def snapshot_to_markdown(snapshot: PortalSnapshot) -> str:
    lines: list[str] = []
    lines.append("# HubSpot Portal Documentation")
    lines.append("")
    lines.append(f"_Pulled at {snapshot.pulled_at}_")
    lines.append("")

    if snapshot.warnings:
        lines.append("## Warnings")
        for w in snapshot.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Data Dictionary")
    for schema in snapshot.object_schemas:
        kind = "Custom" if schema.is_custom else "Standard"
        lines.append(f"### {schema.label} ({kind}, `{schema.object_type}`)")
        if not schema.properties:
            lines.append("_No properties returned._")
            lines.append("")
            continue
        lines.append("| Property | Label | Type | Field Type | Group | Options |")
        lines.append("|---|---|---|---|---|---|")
        for p in schema.properties:
            lines.append(
                f"| {p.name} | {p.label} | {p.type} | {p.field_type} | {p.group_name} | "
                f"{', '.join(p.options)} |"
            )
        lines.append("")

    lines.append("## Workflow Inventory")
    if snapshot.workflows:
        lines.append("| Name | Object Type | Enabled | Re-enrollment | Actions |")
        lines.append("|---|---|---|---|---|")
        for w in snapshot.workflows:
            lines.append(f"| {w.name} | {w.object_type} | {w.enabled} | {w.re_enrollment_enabled} | {len(w.actions)} |")
    else:
        lines.append("_No workflows returned._")
    lines.append("")

    lines.append("## Association Map")
    lines.append(
        "_Association definitions shown here come from each custom object's schema. "
        "Default associations between standard objects are not exposed by this endpoint "
        "and are omitted._"
    )
    any_assoc = False
    lines.append("| From | To (type ID) | Label |")
    lines.append("|---|---|---|")
    for schema in snapshot.object_schemas:
        for a in schema.associations:
            any_assoc = True
            lines.append(f"| {a.from_object} | {a.to_object} | {a.label} |")
    if not any_assoc:
        lines.append("| _None found_ | | |")
    lines.append("")

    lines.append("## Pipelines & Stages")
    if snapshot.pipelines:
        for pl in snapshot.pipelines:
            lines.append(f"### {pl.label} ({pl.object_type})")
            lines.append("| Order | Stage |")
            lines.append("|---|---|")
            for s in pl.stages:
                lines.append(f"| {s.display_order} | {s.label} |")
            lines.append("")
    else:
        lines.append("_No pipelines returned._")
        lines.append("")

    lines.append("## Roles & Permissions Summary")
    lines.append("### Teams")
    if snapshot.teams:
        lines.append("| Team | Member Count |")
        lines.append("|---|---|")
        for t in snapshot.teams:
            lines.append(f"| {t.name} | {t.member_count} |")
    else:
        lines.append("_No teams returned._")
    lines.append("")
    lines.append("### Owners")
    if snapshot.owners:
        lines.append("| Name | Email | Teams | Archived |")
        lines.append("|---|---|---|---|")
        for o in snapshot.owners:
            lines.append(f"| {o.first_name} {o.last_name} | {o.email} | {', '.join(o.teams)} | {o.archived} |")
    else:
        lines.append("_No owners returned._")
    lines.append("")

    return "\n".join(lines)


def snapshot_to_docx(snapshot: PortalSnapshot) -> io.BytesIO:
    doc = Document()

    title = doc.add_heading("HubSpot Portal Documentation", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph(f"Pulled at {snapshot.pulled_at}")

    if snapshot.warnings:
        doc.add_heading("Warnings", level=1)
        for w in snapshot.warnings:
            doc.add_paragraph(w, style="List Bullet")

    doc.add_heading("Data Dictionary", level=1)
    for schema in snapshot.object_schemas:
        kind = "Custom" if schema.is_custom else "Standard"
        doc.add_heading(f"{schema.label} ({kind}, {schema.object_type})", level=2)
        if not schema.properties:
            doc.add_paragraph("No properties returned.")
            continue
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        headers = ["Property", "Label", "Type", "Field Type", "Group"]
        for cell, header in zip(table.rows[0].cells, headers):
            cell.text = header
        for p in schema.properties:
            row = table.add_row().cells
            row[0].text = p.name
            row[1].text = p.label
            row[2].text = p.type
            row[3].text = p.field_type
            row[4].text = p.group_name

    doc.add_heading("Workflow Inventory", level=1)
    if snapshot.workflows:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        for cell, header in zip(table.rows[0].cells, ["Name", "Object Type", "Enabled", "Re-enrollment"]):
            cell.text = header
        for w in snapshot.workflows:
            row = table.add_row().cells
            row[0].text = w.name
            row[1].text = w.object_type
            row[2].text = str(w.enabled)
            row[3].text = str(w.re_enrollment_enabled)
    else:
        doc.add_paragraph("No workflows returned.")

    doc.add_heading("Association Map", level=1)
    doc.add_paragraph(
        "Association definitions shown here come from each custom object's schema. "
        "Default associations between standard objects are not exposed by this endpoint "
        "and are omitted."
    )
    any_assoc = False
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    for cell, header in zip(table.rows[0].cells, ["From", "To (type ID)", "Label"]):
        cell.text = header
    for schema in snapshot.object_schemas:
        for a in schema.associations:
            any_assoc = True
            row = table.add_row().cells
            row[0].text = a.from_object
            row[1].text = a.to_object
            row[2].text = a.label
    if not any_assoc:
        doc.add_paragraph("None found.")

    doc.add_heading("Pipelines & Stages", level=1)
    if snapshot.pipelines:
        for pl in snapshot.pipelines:
            doc.add_heading(f"{pl.label} ({pl.object_type})", level=2)
            table = doc.add_table(rows=1, cols=2)
            table.style = "Light Grid Accent 1"
            for cell, header in zip(table.rows[0].cells, ["Order", "Stage"]):
                cell.text = header
            for s in pl.stages:
                row = table.add_row().cells
                row[0].text = str(s.display_order)
                row[1].text = s.label
    else:
        doc.add_paragraph("No pipelines returned.")

    doc.add_heading("Roles & Permissions Summary", level=1)
    doc.add_heading("Teams", level=2)
    if snapshot.teams:
        table = doc.add_table(rows=1, cols=2)
        table.style = "Light Grid Accent 1"
        for cell, header in zip(table.rows[0].cells, ["Team", "Member Count"]):
            cell.text = header
        for t in snapshot.teams:
            row = table.add_row().cells
            row[0].text = t.name
            row[1].text = str(t.member_count)
    else:
        doc.add_paragraph("No teams returned.")

    doc.add_heading("Owners", level=2)
    if snapshot.owners:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        for cell, header in zip(table.rows[0].cells, ["Name", "Email", "Teams", "Archived"]):
            cell.text = header
        for o in snapshot.owners:
            row = table.add_row().cells
            row[0].text = f"{o.first_name} {o.last_name}".strip()
            row[1].text = o.email
            row[2].text = ", ".join(o.teams)
            row[3].text = str(o.archived)
    else:
        doc.add_paragraph("No owners returned.")

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
