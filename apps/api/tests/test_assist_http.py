"""The "Fill from earlier steps" / "Suggest" endpoints, with a fake model."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from archscope_api.routers.deps import AiBackend, get_ai_client

DISCOVERY = {
    "client_name": "Acme Dental",
    "business_type": "Dental group",
    "sections": {
        "Processes": {
            "answers": {
                "sales_pipeline_stages": {
                    "selected": [],
                    "other": "",
                    "notes": "Consult, Treatment plan, Booked",
                    "flagged": False,
                }
            },
            "notes": "",
            "edge_cases": "",
        }
    },
}


def _fake_claude(answer: dict[str, Any]) -> tuple[AiBackend, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(answer))])

    return AiBackend("anthropic", SimpleNamespace(messages=SimpleNamespace(create=create))), calls


async def _post(app: FastAPI, path: str, body: dict[str, Any]) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        return await http.post(f"/api/v1/assist/{path}", json=body)


async def test_stage_planner_fills_an_empty_planner_from_discovery(app: FastAPI) -> None:
    ai, calls = _fake_claude(
        {"stages": [{"name": "Consult", "forecast": 20, "fields": ["Treatment type"]}, {"name": "Closed Won", "forecast": 100}]}
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    response = await _post(app, "stage-planner", {"context": {"discovery": DISCOVERY}, "stages": []})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["name"] for s in body["stages"]] == ["Consult", "Closed Won"]
    assert body["stages"][0]["fields"] == ["Treatment type"]
    sent = calls[0]["messages"][0]["content"]
    assert "Consult, Treatment plan, Booked" in sent  # the discovery answer reached the model


async def test_proposal_suggestion_never_overwrites_typed_text(app: FastAPI, client: AsyncClient) -> None:
    proposal = (await client.get("/api/v1/proposals/default")).json()
    proposal["problem_statement"] = "Typed by the seller"
    ai, _ = _fake_claude(
        {"problem_statement": "Model", "executive_summary": "A summary", "assumptions": ["Portal access in 5 days"]}
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    response = await _post(app, "proposal", {"context": {"discovery": DISCOVERY}, "proposal": proposal})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposal"]["problem_statement"] == "Typed by the seller"
    assert body["proposal"]["executive_summary"] == "A summary"
    assert "executive_summary" in body["changed"]


async def test_architecture_adds_to_the_selection(app: FastAPI) -> None:
    ai, _ = _fake_claude(
        {"standard_objects": ["Deal", "Ticket"], "integrations": ["Dentrix"], "record_volumes": {"Contact": 12000}}
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    inputs = {"standard_objects": ["Contact", "Deal"], "currencies": ["USD"]}
    response = await _post(app, "architecture", {"context": {"discovery": DISCOVERY}, "inputs": inputs})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["inputs"]["standard_objects"] == ["Contact", "Deal", "Ticket"]
    assert body["inputs"]["integrations"] == ["Dentrix"]
    assert body["inputs"]["record_volumes"] == {"Contact": 12000}
    assert body["added"] == 3


async def test_no_context_is_a_clear_422(app: FastAPI) -> None:
    ai, calls = _fake_claude({})
    app.dependency_overrides[get_ai_client] = lambda: ai
    response = await _post(app, "stage-planner", {"context": {}, "stages": []})
    assert response.status_code == 422
    assert response.json()["type"].endswith("/no-context")
    assert calls == []  # the model isn't called with nothing to read


async def test_unreadable_answer_is_a_problem(app: FastAPI) -> None:
    def create(**_: Any) -> SimpleNamespace:
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Sorry, no.")])

    app.dependency_overrides[get_ai_client] = lambda: AiBackend(
        "anthropic", SimpleNamespace(messages=SimpleNamespace(create=create))
    )
    response = await _post(app, "stage-planner", {"context": {"discovery": DISCOVERY}, "stages": []})
    assert response.status_code == 502
    assert response.json()["type"].endswith("/ai-incomplete")


async def test_industry_templates_list_and_apply(client: AsyncClient) -> None:
    listing = (await client.get("/api/v1/industry-templates")).json()
    assert {"saas", "healthcare"} <= {i["id"] for i in listing["industries"]}
    assert [s["id"] for s in listing["sizes"]] == ["smb", "mid_market", "enterprise"]

    response = await client.post(
        "/api/v1/industry-templates/discovery", json={"industry": "healthcare", "size": "smb", "notes": DISCOVERY}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["notes"]["business_type"] == "Dental group"  # typed value kept
    assert (
        body["notes"]["sections"]["Processes"]["answers"]["sales_pipeline_stages"]["notes"] == "Consult, Treatment plan, Booked"
    )
    assert "HIPAA" in body["notes"]["sections"]["Data"]["answers"]["compliance"]["selected"]
    assert body["filled"] > 0

    proposal = (await client.get("/api/v1/proposals/default")).json()
    applied = await client.post("/api/v1/industry-templates/proposal", json={"industry": "saas", "proposal": proposal})
    assert applied.status_code == 200, applied.text
    assert "scope" in applied.json()["changed"]

    unknown = await client.post("/api/v1/industry-templates/proposal", json={"industry": "nope", "proposal": proposal})
    assert unknown.status_code == 422
    assert unknown.json()["type"].endswith("/unknown-template")


async def test_project_tasks_skip_existing_and_unknown_stages(app: FastAPI) -> None:
    ai, _ = _fake_claude(
        {
            "tasks": [
                {"stage": "discover", "title": "Confirm data owner per clinic", "source": "Open question"},
                {"stage": "discover", "title": "confirm data owner per clinic!", "source": "duplicate"},
                {"stage": "build", "title": "Set up consent subscription types", "source": "GDPR answer"},
                {"stage": "nowhere", "title": "Ignored", "source": ""},
            ]
        }
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    body = {"context": {"discovery": DISCOVERY}, "tasks": [{"stage": "build", "title": "Set up consent subscription types"}]}
    response = await _post(app, "project-tasks", body)
    assert response.status_code == 200, response.text
    assert [(t["stage"], t["title"]) for t in response.json()["tasks"]] == [("discover", "Confirm data owner per clinic")]


async def test_company_overview_reads_the_website(app: FastAPI, monkeypatch: Any) -> None:
    from archscope_api.services import website

    seen: list[str] = []

    def fake_read(url: str) -> Any:
        seen.append(url)
        return website.WebsiteSnapshot(url="https://brightsmiles.example/", title="Bright Smiles Dental", text="12 clinics")

    monkeypatch.setattr(website, "read_homepage", fake_read)
    ai, calls = _fake_claude({"name": "Bright Smiles", "summary": "Dental group.", "highlights": ["12 clinics", ""]})
    app.dependency_overrides[get_ai_client] = lambda: ai
    response = await _post(app, "company-overview", {"website": "brightsmiles.example"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overview"]["name"] == "Bright Smiles"
    assert body["overview"]["highlights"] == ["12 clinics"]
    assert body["overview"]["offerings"] == []
    assert "Bright Smiles Dental" in calls[0]["messages"][0]["content"]
    assert seen == ["brightsmiles.example"]


async def test_company_overview_unreadable_site_is_a_clear_422(app: FastAPI, monkeypatch: Any) -> None:
    from archscope_api.services import website

    def fail(url: str) -> Any:
        raise website.WebsiteError("That address didn't respond.")

    monkeypatch.setattr(website, "read_homepage", fail)
    ai, calls = _fake_claude({})
    app.dependency_overrides[get_ai_client] = lambda: ai
    response = await _post(app, "company-overview", {"website": "nope.example"})
    assert response.status_code == 422
    assert response.json()["type"].endswith("/website-unreadable")
    assert calls == []


async def test_schedule_suggests_new_meetings_only_and_tidies_them(app: FastAPI) -> None:
    ai, calls = _fake_claude(
        {
            "meetings": [
                {"title": "Kickoff & goals", "type": "kickoff", "stage": "discover", "week": 1},
                {
                    "title": "Pipeline design review",
                    "type": "Design",
                    "stage": "design",
                    "week": "3",
                    "duration_minutes": 90,
                    "agenda": ["Stages", "stages", ""],
                    "attendees": ["Client sales lead"],
                },
                {"title": "Mystery", "type": "party", "stage": "moon", "week": 900},
            ]
        }
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    body = {
        "context": {"discovery": DISCOVERY},
        "settings": {"start_date": "2026-11-02", "cadence": "Weekly", "meeting_count": 6},
        "meetings": [{"title": "Kickoff & goals", "type": "kickoff", "date": "2026-11-03"}],
    }
    response = await _post(app, "schedule", body)
    assert response.status_code == 200, response.text
    meetings = response.json()["meetings"]
    assert [m["title"] for m in meetings] == ["Pipeline design review", "Mystery"]
    assert meetings[0]["type"] == "design"
    assert meetings[0]["week"] == 3
    assert meetings[0]["agenda"] == ["Stages"]
    assert meetings[1]["type"] == "other"
    assert meetings[1]["stage"] == ""
    assert meetings[1]["week"] is None
    sent = calls[0]["messages"][0]["content"]
    assert "Consult, Treatment plan, Booked" in sent
    assert "2026-11-02" in sent


async def test_schedule_works_from_settings_alone(app: FastAPI) -> None:
    ai, _ = _fake_claude({"meetings": [{"title": "Kickoff", "type": "kickoff", "week": 1}]})
    app.dependency_overrides[get_ai_client] = lambda: ai
    response = await _post(app, "schedule", {"context": {}, "settings": {"cadence": "Weekly"}})
    assert response.status_code == 200, response.text
    assert response.json()["meetings"][0]["title"] == "Kickoff"


async def test_schedule_meeting_fills_blanks_and_appends_new_items(app: FastAPI) -> None:
    ai, _ = _fake_claude(
        {
            "purpose": "Model purpose",
            "explain": "Why the pipeline matters",
            "agenda": ["Review stages", "Agree exit criteria"],
            "follow_ups": ["Send recap"],
        }
    )
    app.dependency_overrides[get_ai_client] = lambda: ai
    body = {
        "context": {"discovery": DISCOVERY},
        "meeting": {"title": "Pipeline review", "purpose": "Typed purpose", "agenda": ["review stages"]},
        "other_meetings": [{"title": "Kickoff", "date": "2026-11-03"}],
    }
    response = await _post(app, "schedule-meeting", body)
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["meeting"]["purpose"] == "Typed purpose"
    assert out["meeting"]["agenda"] == ["review stages", "Agree exit criteria"]
    assert out["meeting"]["explain"] == "Why the pipeline matters"
    assert set(out["changed"]) == {"agenda", "explain", "follow_ups"}
