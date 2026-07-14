import pytest


@pytest.mark.asyncio
async def test_equipment_incident_work_order_and_dashboard_api(api_client):
    equipment = await api_client.get("/api/equipment")
    assert equipment.status_code == 200
    assert len(equipment.json()) == 5

    incident_payload = {
        "equipment_code": "CNC-01",
        "incident_type": "vibration",
        "title": "Spindle vibration high",
        "description": "Spindle vibration exceeded threshold",
        "severity": "P1",
        "production_batch_no": "BATCH-20260714-001",
    }
    first = await api_client.post("/api/incidents", json=incident_payload)
    duplicate = await api_client.post("/api/incidents", json=incident_payload)

    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True
    incident_id = first.json()["incident"]["id"]

    timeline = await api_client.get(f"/api/incidents/{incident_id}/timeline")
    assert timeline.status_code == 200
    assert any(event["event_type"] == "INCIDENT_DUPLICATED" for event in timeline.json())

    work_order = await api_client.post(
        "/api/work-orders",
        json={"incident_id": incident_id, "title": "Inspect spindle", "description": "Inspect spindle vibration", "priority": "P1"},
    )
    assert work_order.status_code == 201
    work_order_id = work_order.json()["id"]

    assigned = await api_client.post(f"/api/work-orders/{work_order_id}/assign", json={"assigned_team": "Maintenance", "assignee": "Li"})
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "ASSIGNED"

    summary = await api_client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    assert summary.json()["total_incidents"] >= 10
    assert summary.json()["total_work_orders"] >= 5

    severity = await api_client.get("/api/dashboard/severity-distribution")
    assert severity.status_code == 200
    assert any(bucket["severity"] == "P1" for bucket in severity.json())

    sla = await api_client.get("/api/dashboard/sla-metrics")
    assert sla.status_code == 200
    assert {"overdue_work_orders", "due_soon_work_orders", "overdue_incidents"} <= set(sla.json())


@pytest.mark.asyncio
async def test_internal_token_and_resume_url_not_leaked(api_client, internal_token):
    incident = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-02",
            "incident_type": "approval",
            "title": "Approval required",
            "description": "Requires manual approval",
            "severity": "P1",
        },
    )
    incident_id = incident.json()["incident"]["id"]

    denied = await api_client.post("/api/internal/approvals/register", json={"incident_id": incident_id, "resume_url": "http://n8n/resume/secret"})
    assert denied.status_code == 401

    allowed = await api_client.post(
        "/api/internal/approvals/register",
        headers={"x-internal-token": internal_token},
        json={"incident_id": incident_id, "resume_url": "http://n8n/resume/secret"},
    )
    assert allowed.status_code == 200
    assert "resume_url" not in allowed.text
    assert "http://n8n/resume/secret" not in allowed.text

    pending = await api_client.get("/api/approvals/pending")
    assert pending.status_code == 200
    assert "resume_url" not in pending.text
    assert "http://n8n/resume/secret" not in pending.text

    approved = await api_client.post(f"/api/approvals/{allowed.json()['id']}/approve", json={"approver": "manager", "comment": "ok"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    repeated = await api_client.post(f"/api/approvals/{allowed.json()['id']}/approve", json={"approver": "manager", "comment": "again"})
    assert repeated.status_code == 409


@pytest.mark.asyncio
async def test_demo_and_openapi_are_available(api_client):
    scenarios = await api_client.get("/api/demo/scenarios")
    assert scenarios.status_code == 200
    assert len(scenarios.json()) == 2

    trigger = await api_client.post("/api/demo/scenarios/cnc-vibration-p1/trigger")
    assert trigger.status_code == 200
    assert trigger.json()["incident"]["incident_no"].startswith("INC-")

    openapi = await api_client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/incidents" in openapi.json()["paths"]
