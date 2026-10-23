"""Project insights: stage, scoping progress, portal health and open tasks,
derived from what each project has saved."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from archscope_api.services.project_insights import TOOLS


async def _save(client: AsyncClient, pid: str, module: str, data: dict[str, Any], version: int = 0) -> None:
    saved = await client.put(f"/api/v1/projects/{pid}/state/{module}", json={"data": data, "version": version})
    assert saved.status_code == 200, saved.text


async def _doc(client: AsyncClient, pid: str, document_type: str) -> None:
    upload = await client.post(
        f"/api/v1/projects/{pid}/documents",
        params={"document_type": document_type, "filename": "x.txt"},
        content=b"x",
        headers={"Content-Type": "text/plain"},
    )
    assert upload.status_code == 201


async def _insights(client: AsyncClient) -> dict[str, dict[str, Any]]:
    response = await client.get("/api/v1/projects/insights")
    assert response.status_code == 200
    return {i["project_id"]: i for i in response.json()}


async def test_a_new_project_has_not_started(client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Fresh"})).json()["id"]
    i = (await _insights(client))[pid]
    assert (i["stage"], i["progress"], i["tools_started"], i["open_tasks"]) == ("Discover", 0, 0, 0)
    assert i["tools_total"] == len(TOOLS)
    assert i["health"] == {"status": "not_started", "score": None, "high": 0, "medium": 0, "low": 0}


async def test_stage_progress_health_and_tasks_follow_saved_work(client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    await _save(client, pid, "discovery", {"clientName": "Acme"})
    await _save(client, pid, "stage_planner", {})  # an empty save isn't work
    await _doc(client, pid, "Architecture Blueprint")  # a saved deliverable starts its tool (Design)
    await _save(
        client,
        pid,
        "portal",
        {
            "snapshot": {"objects": []},
            "auditedAt": "2026-10-20T10:00:00Z",
            "findings": [{"severity": "Medium"}, {"severity": "Medium"}, {"severity": "Low"}],
            "propertyAudit": None,
        },
    )
    await _save(
        client,
        pid,
        "tasks",
        {
            "tasks": [
                {"id": "1", "stage": "discover", "title": "a", "done": True},
                {"id": "2", "stage": "design", "title": "b", "done": False},
            ]
        },
    )

    i = (await _insights(client))[pid]
    assert i["stage"] == "Design"  # furthest started stage
    assert i["tools_started"] == 3  # discovery, portal auditor, architecture generator
    assert i["progress"] == round(100 * 3 / len(TOOLS))
    assert i["open_tasks"] == 1
    assert i["health"] == {"status": "healthy", "score": 100 - 8 - 1, "high": 0, "medium": 2, "low": 1}

    await _save(
        client,
        pid,
        "portal",
        {"snapshot": {}, "auditedAt": "x", "findings": [{"severity": "High"}] * 8, "propertyAudit": {"rows": []}},
        version=1,
    )
    i = (await _insights(client))[pid]
    assert i["health"]["status"] == "needs_review"
    assert i["health"]["score"] == 0  # never below 0
    assert i["tools_started"] == 4  # the property audit now has work too


async def test_insights_stay_in_the_workspace(client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Mine"})).json()["id"]
    assert set(await _insights(client)) == {pid}


async def test_dashboard_of_a_new_project_is_empty(client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Blank"})).json()["id"]
    d = (await client.get(f"/api/v1/projects/{pid}/dashboard")).json()
    assert d["insight"]["progress"] == 0
    assert (d["continue_page"], d["continue_label"]) == ("discovery", "Continue in Discovery Call Assistant")
    assert d["workstreams"] == []
    assert d["completion"]["scoped"] == d["completion"]["in_progress"] == 0
    assert d["completion"]["outstanding"] == 100
    assert [s["generated"] for s in d["documents_by_stage"]] == [0, 0, 0, 0, 0]
    assert all(s["outstanding"] == len(s["outstanding_names"]) for s in d["documents_by_stage"])
    assert d["activity"] == []
    assert [c["role"] for c in d["contributors"]] == ["In charge"]  # the creator is in charge


async def test_dashboard_reads_the_projects_saved_work(client: AsyncClient) -> None:
    pid = (await client.post("/api/v1/projects", json={"name": "Acme"})).json()["id"]
    await _save(client, pid, "discovery", {"clientName": "Acme"})
    await _doc(client, pid, "Discovery Checklist")
    await _doc(client, pid, "Proposal & SOW")
    await _save(client, pid, "portal", {"snapshot": {}, "auditedAt": "2026-10-20T10:00:00Z", "findings": [{"severity": "High"}]})
    await _save(
        client,
        pid,
        "tasks",
        {
            "tasks": [
                {
                    "id": "1",
                    "stage": "discover",
                    "title": "Kick-off",
                    "done": True,
                    "doneAt": "2026-10-21T09:00:00Z",
                    "doneBy": "Ana",
                },
                {"id": "2", "stage": "discover", "title": "Send recap", "done": False},
                {"id": "3", "stage": "design", "title": "Draft model", "done": False},
            ],
            "stages": {"design": {"ownerId": None, "startedOn": None, "finishedOn": None}},
        },
    )
    d = (await client.get(f"/api/v1/projects/{pid}/dashboard")).json()

    assert d["insight"]["stage"] == "Propose"
    assert d["continue_page"] == "proposal"  # Propose has one tool, and it's started
    assert [(w["stage"], w["title"], w["done"], w["total"]) for w in d["workstreams"]] == [("Discover", "Send recap", 1, 2)]
    assert [p["name"] for p in d["workstreams"][0]["people"]] == ["Ana"]

    c = d["completion"]
    assert c["scoped"] + c["in_progress"] + c["outstanding"] == 100
    assert c["scoped"] == round(100 * 2 / c["deliverables"])
    by_stage = {s["stage"]: s for s in d["documents_by_stage"]}
    assert by_stage["Discover"]["generated"] == 1
    assert "Discovery Checklist" not in by_stage["Discover"]["outstanding_names"]
    assert (by_stage["Propose"]["generated"], by_stage["Propose"]["outstanding"]) == (1, 0)

    assert d["documents"] == 2
    assert d["contributors"][0]["documents"] == 2
    kinds = [a["kind"] for a in d["activity"]]
    assert {"document", "task", "audit", "edit"} <= set(kinds)
    times = [a["at"] for a in d["activity"]]
    assert times == sorted(times, reverse=True)
    assert d["insight"]["health"]["status"] == "needs_review"


async def test_dashboard_is_workspace_scoped(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/projects/not-a-project/dashboard")).status_code == 404
