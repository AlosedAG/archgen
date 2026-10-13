"""Discovery config + evaluate endpoints: the web form's view of the
question bank, follow-ups, tasks and build-order settings, and what a set
of notes triggers (follow-ups, required tasks, checklist, build order)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_config_lists_questions_follow_ups_tasks_and_build_settings(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/discovery/config")).json()
    assert [s["name"] for s in body["question_bank"]["sections"]] == ["Goals", "Data", "Processes", "Solutions Design"]
    assert body["question_bank"]["sections"][1]["description"].startswith("Understand the data landscape")
    gdpr = next(f for f in body["follow_ups"] if f["id"] == "gdpr_lawful_basis")
    assert gdpr["home_section"] == "Data"
    assert gdpr["input"] == "multiselect"
    assert any(t["id"] == "gdpr_consent_setup" for t in body["tasks"])
    build = body["build_order"]
    assert build["done_status"] in build["statuses"]
    assert build["sections"][0]["id"] == "assets"
    assert build["templates"]["gdpr_bundle"] == "GDPR asset bundle"


async def test_evaluate_blank_notes_triggers_nothing(client: AsyncClient) -> None:
    body = (await client.post("/api/v1/discovery/evaluate", json={})).json()
    assert body["follow_ups"] == {}
    assert body["tasks"] == []
    assert [s["rows"] for s in body["checklist"]] == [[], []]
    assert all(not s["items"] for s in body["build_order"]["sections"])


async def test_evaluate_reveals_follow_ups_and_builds_everything(client: AsyncClient) -> None:
    notes = {
        "client_name": "Bright Smiles",
        "project_type": "CRM Migration to HubSpot",
        "done_build_items": ["gdpr_form_consent"],
        "sections": {
            "Data": {"answers": {"data_regions": {"selected": ["EU / UK"]}}},
            "Solutions Design": {"answers": {"integrations": {"selected": ["Salesforce"]}}},
        },
    }
    body = (await client.post("/api/v1/discovery/evaluate", json=notes)).json()
    assert body["follow_ups"]["data_regions"] == ["gdpr_lawful_basis", "gdpr_consent_capture", "data_residency"]
    assert body["revealed_by"]["gdpr_lawful_basis"] == ["EU / UK"]
    consent = next(t for t in body["tasks"] if t["task"]["id"] == "gdpr_consent_setup")
    assert consent["reasons"] == ["Where are their customers / contacts located? → EU / UK"]
    scope = next(s for s in body["checklist"] if s["title"] == "Scope items")
    assert scope["rows"][0]["Task"] == "Integration: Salesforce"
    order = body["build_order"]
    assert order["schema"] == "archscope.build_order/v1"
    assert order["title"] == "Bright Smiles — CRM Migration to HubSpot — Build Order"
    item = next(i for s in order["sections"] for i in s["items"] if i["id"] == "gdpr_form_consent")
    assert item["done"] is True
    assert item["template_label"] == "GDPR asset bundle"
    assert body["build_order_sections"][0]["title"] == "Assets to be created"


async def test_evaluate_rejects_unknown_fields(client: AsyncClient) -> None:
    response = await client.post("/api/v1/discovery/evaluate", json={"done_items": []})
    assert response.status_code == 422
