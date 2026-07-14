from sqlalchemy import select

from factory_hub.domain.enums import RpaStatus
from factory_hub.domain.models import RpaRun, WorkOrder
from factory_hub.schemas import RpaWorkOrderResponse


async def test_public_rpa_runs_list_exposes_audit_without_secrets(api_client, db_session):
    work_order = (await db_session.execute(select(WorkOrder).order_by(WorkOrder.id))).scalars().first()
    run = RpaRun(
        work_order_id=work_order.id,
        status=RpaStatus.SUCCEEDED.value,
        external_id="MES-WO-20260714-9001",
        screenshot_path="/artifacts/rpa/success-9001.png",
        steps=[{"step": "submit_form", "status": "ok"}],
    )
    db_session.add(run)
    await db_session.commit()

    response = await api_client.get("/api/rpa-runs")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["external_id"] == "MES-WO-20260714-9001"
    assert "password" not in str(body).lower()
    assert "token" not in str(body).lower()


async def test_public_incident_analysis_runs_return_saved_agent_result(api_client):
    created = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-01",
            "incident_type": "vibration",
            "title": "Stage 6 analysis display",
            "description": "spindle vibration value 9.2 mm/s",
            "severity": "P2",
            "production_batch_no": "BATCH-20260714-001",
        },
    )
    incident_id = created.json()["incident"]["id"]
    analyzed = await api_client.post(f"/api/incidents/{incident_id}/analyze", json={"force": True})
    assert analyzed.status_code == 200

    response = await api_client.get(f"/api/incidents/{incident_id}/analysis-runs")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["incident_id"] == incident_id
    assert body[0]["agent_output"]["summary"]
    assert body[0]["final_severity"] == "P1"


async def test_demo_rpa_fallback_returns_real_audit_payload(api_client, monkeypatch):
    async def fake_rpa(session, settings, work_order_id, reason):
        run = RpaRun(
            work_order_id=work_order_id,
            status=RpaStatus.SUCCEEDED.value,
            external_id="MES-WO-20260714-9100",
            screenshot_path="/artifacts/rpa/success-9100.png",
            steps=[{"step": "login", "status": "ok"}, {"step": "submit", "status": "ok"}],
        )
        session.add(run)
        work_order = await session.get(WorkOrder, work_order_id)
        work_order.external_id = run.external_id
        work_order.creation_method = "RPA"
        await session.commit()
        return RpaWorkOrderResponse(
            success=True,
            external_id=run.external_id,
            screenshot_path=run.screenshot_path,
            steps=run.steps,
        ).model_dump()

    monkeypatch.setattr("factory_hub.api.routes.workflow.create_work_order_with_rpa", fake_rpa)

    response = await api_client.post("/api/demo/rpa-fallback")

    assert response.status_code == 200
    body = response.json()
    assert body["work_order"]["creation_method"] == "RPA"
    assert body["work_order"]["external_id"] == "MES-WO-20260714-9100"
    assert body["rpa_run"]["status"] == "SUCCEEDED"
    assert body["rpa_result"]["success"] is True
