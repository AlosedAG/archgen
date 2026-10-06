"""Schema <-> domain mapping is lossless, and the API's enumerations can't
drift from the domain's: any new value the domain can emit must be added
to the contract (or responses would fail validation in production)."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from typing import Any, get_args

import pytest
from httpx import AsyncClient

from archscope_api.schemas import audit, diagram, discovery, portal, proposal, report
from archscope_api.schemas.blueprint import Blueprint
from archscope_domain import discovery as ddisc
from archscope_domain import discovery_config, models
from archscope_domain import property_audit as dpa
from archscope_domain import proposal as dprop
from archscope_domain.audit import PortalAuditor
from archscope_domain.property_audit import run_property_audit
from archscope_domain.report import _rate_portal_health
from archscope_domain.rules import RulesEngine

Golden = Callable[[str], Any]


# ---- enumerations pinned to the domain ------------------------------------------


@pytest.mark.parametrize(
    ("literal", "domain_values"),
    [
        (portal.Severity, models.SEVERITIES),
        (audit.PropertyRating, [dpa.RATING_KEEP, dpa.RATING_REVIEW, dpa.RATING_REMOVE]),
        (proposal.ScopeStatus, dprop.SCOPE_STATUSES),
        (proposal.Billing, dprop.BILLING_OPTIONS),
        (proposal.KpiType, dprop.KPI_TYPES),
        (proposal.DocumentType, dprop.DOCUMENT_TYPES),
        (proposal.Coverage, [dprop.COVERAGE_NONE, *dprop.COVERAGE_LABELS.values()]),
        (discovery.HubSpotModule, ddisc.HUBSPOT_MODULES),
        (discovery.InputType, discovery_config.INPUT_TYPES),
        (diagram.NodeKind, ["Standard", "Custom", "Activity"]),
    ],
)
def test_literal_matches_domain(literal: Any, domain_values: list[str]) -> None:
    assert set(get_args(literal)) == set(domain_values)


def test_health_ratings_cover_every_rating_the_domain_produces() -> None:
    produced = {_rate_portal_health(counts)[0] for counts in ({"High": 1}, {"Medium": 6}, {"Medium": 1}, {"Low": 1}, {})} | {
        "Not Yet Audited"
    }
    assert produced == set(get_args(report.HealthRating))


def test_proposal_rows_cover_every_domain_column() -> None:
    """Every column of every domain table is a typed field (by title)."""
    for table, row_cls in proposal.ProposalDocument._TABLES.items():
        titles = {f.title for f in row_cls.model_fields.values()}
        assert titles == set(dprop.BLANK_ROWS[table]), table


# ---- lossless round trips ---------------------------------------------------------


def test_blueprint_round_trip(golden: Golden) -> None:
    domain = Blueprint.model_validate(golden("blueprint")["blueprint"]).to_domain()
    assert isinstance(domain, models.Blueprint)
    assert isinstance(domain.custom_objects[0], models.CustomObjectDef)
    assert Blueprint.from_domain(domain).to_domain() == domain


def test_snapshot_round_trip(golden: Golden) -> None:
    domain = portal.PortalSnapshot.model_validate(golden("docgen")["snapshot"]).to_domain()
    assert isinstance(domain.object_schemas[0].properties[0], models.PortalPropertyDef)
    assert portal.PortalSnapshot.from_domain(domain).to_domain() == domain


def test_default_proposal_round_trips_to_identical_domain_document() -> None:
    domain = dprop.default_proposal()
    assert proposal.ProposalDocument.from_domain(domain).to_domain() == domain


def test_proposal_rows_use_snake_case_on_the_wire() -> None:
    doc = proposal.ProposalDocument.from_domain(dprop.default_proposal()).model_dump()
    assert set(doc["scope"][0]) == {
        "id",
        "workstream",
        "item",
        "status",
        "quantity_limit",
        "tools_techniques",
        "requirement_ids",
        "acceptance_criteria",
        "milestone",
    }


def test_unknown_fields_are_rejected_not_dropped() -> None:
    with pytest.raises(ValueError, match="extra"):
        proposal.ScopeRow.model_validate({"item": "x", "itme": "typo"})


# ---- responses == serialized domain results ----------------------------------------


async def _snapshot(client: AsyncClient) -> dict[str, Any]:
    response = await client.post("/api/v1/portal/snapshot", headers={"X-HubSpot-Token": "t"})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_snapshot_pull_maps_every_field(client: AsyncClient, portal_reader: Any) -> None:
    from archscope_domain.docgen import DocumentationGenerator

    body = await _snapshot(client)
    expected = dataclasses.asdict(DocumentationGenerator(portal_reader).build_snapshot())
    assert {k: v for k, v in body.items() if k != "pulled_at"} == {k: v for k, v in expected.items() if k != "pulled_at"}


async def test_audit_response_equals_domain_audit(client: AsyncClient, portal_reader: Any) -> None:
    snapshot = await _snapshot(client)
    response = await client.post("/api/v1/audits", json={"snapshot": snapshot}, headers={"X-HubSpot-Token": "t"})
    assert response.status_code == 200, response.text
    domain_snapshot = portal.PortalSnapshot.model_validate(snapshot).to_domain()
    expected = [dataclasses.asdict(f) for f in PortalAuditor(portal_reader, RulesEngine()).run(domain_snapshot)]
    body = response.json()
    assert body["findings"] == expected
    assert sum(body["by_severity"].values()) == len(expected) == sum(body["by_area"].values())
    assert list(body["by_severity"]) == models.SEVERITIES


async def test_property_audit_response_equals_domain_and_exports(client: AsyncClient, portal_reader: Any) -> None:
    snapshot = await _snapshot(client)
    response = await client.post("/api/v1/property-audits", json={"snapshot": snapshot}, headers={"X-HubSpot-Token": "t"})
    assert response.status_code == 200, response.text
    expected = dataclasses.asdict(
        run_property_audit(portal_reader, portal.PortalSnapshot.model_validate(snapshot).to_domain(), RulesEngine())
    )
    body = response.json()
    assert {k: v for k, v in body.items() if k != "generated_at"} == {k: v for k, v in expected.items() if k != "generated_at"}

    for fmt, media in (("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
        export = await client.post(
            f"/api/v1/property-audits/export?format={fmt}", json={"result": body, "project_name": "Acme Co"}
        )
        assert export.status_code == 200
        assert media in export.headers["content-type"]
        assert export.headers["content-disposition"] == f'attachment; filename="Acme_Co_property_audit.{fmt}"'


async def test_proposal_analysis_equals_domain(client: AsyncClient) -> None:
    doc = (await client.get("/api/v1/proposals/default")).json()
    doc = (
        await client.post(
            "/api/v1/proposals/scope/library-items", json={"proposal": doc, "items": [dprop.SCOPE_LIBRARY[0]["Item"]]}
        )
    ).json()
    doc["milestones"][0].update(milestone="M1", fee=11500)
    doc["milestones"][1].update(milestone="M2", fee=2500.5)
    doc["addons"] = [{"service": "Support", "includes": "", "cost": 500, "billing": "Monthly", "add_to_total": True}]
    doc["discount_pct"] = 12.5
    response = await client.post("/api/v1/proposals/analysis", json={"proposal": doc})
    assert response.status_code == 200, response.text
    body = response.json()

    domain_doc = proposal.ProposalDocument.model_validate(doc).to_domain()
    assert body["pricing"] == dprop.pricing_summary(domain_doc)
    assert body["warnings"] == dprop.validate(domain_doc)
    assert [r["coverage"] for r in body["coverage"]] == [r["Coverage"] for r in dprop.requirement_coverage(domain_doc)]
    expected_groups = dprop.scope_by_status(domain_doc)
    assert {s: [r["item"] for r in rows] for s, rows in body["scope_by_status"].items()} == {
        s: [r["Item"] for r in rows] for s, rows in expected_groups.items()
    }


async def test_proposal_pdf_renders(client: AsyncClient) -> None:
    doc = (await client.get("/api/v1/proposals/default")).json()
    doc["client"]["company"] = "Acme"
    response = await client.post("/api/v1/proposals/pdf", json={"proposal": doc})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-disposition"] == 'attachment; filename="Acme_Proposal_Statement_of_Work.pdf"'


async def test_wrd_import_equals_domain(client: AsyncClient) -> None:
    doc = (await client.get("/api/v1/proposals/default")).json()
    wrd = {"Goals": [{"Goal": "One source of truth"}], "Customer Requirements": [{"Requirement": "Sync contacts nightly"}]}
    response = await client.post("/api/v1/proposals/import/wrd", json={"proposal": doc, "wrd": wrd})
    expected = dprop.import_from_wrd(dprop.default_proposal(), wrd)
    assert proposal.ProposalDocument.model_validate(response.json()).to_domain() == expected


async def test_question_bank_mirrors_config(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/discovery/question-bank")).json()
    bank = ddisc.question_bank()
    assert [s["name"] for s in body["sections"]] == list(bank.sections)
    assert body["other_option"] == bank.other_option
    first = bank.sections["Goals"][0]
    assert body["sections"][0]["questions"][0] == {
        "id": first.key,
        "label": first.label,
        "hint": first.hint,
        "input": first.input,
        "options": list(first.options),
    }


def test_report_context_name_counts_are_objects() -> None:
    raw = json.loads(
        '{"label":"Contact","object_type":"contacts","is_custom":false,"property_count":2,"top_groups":[["Info",2]]}'
    )
    assert report.ObjectSummary.model_validate(raw).top_groups[0].model_dump() == {"name": "Info", "count": 2}
