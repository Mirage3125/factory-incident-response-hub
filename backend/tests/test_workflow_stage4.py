from datetime import timedelta

import pytest
from sqlalchemy import func, select

from factory_hub.domain.enums import RpaStatus, Severity, WorkOrderCreationMethod, WorkOrderStatus
from factory_hub.domain.models import KnowledgeCase, Notification, RpaRun, WorkflowEvent, WorkOrder
from factory_hub.services.core import calculate_sla_due, next_number, utcnow
from factory_hub.config import get_settings


@pytest.mark.asyncio
async def test_approval_decision_does_not_leak_resume_url_and_records_unreachable_n8n(api_client, db_session, internal_token):
    incident = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-01",
            "incident_type": "stage4-approval",
            "title": "Approval resume validation",
            "description": "vibration=9.4 mm/s",
            "severity": "P1",
        },
    )
    incident_id = incident.json()["incident"]["id"]
    registered = await api_client.post(
        "/api/internal/approvals/register",
        headers={"X-Internal-Token": internal_token},
        json={"incident_id": incident_id, "resume_url": "http://127.0.0.1:9/webhook-waiting/secret-token"},
    )
    assert registered.status_code == 200
    assert "secret-token" not in registered.text

    approved = await api_client.post(
        f"/api/approvals/{registered.json()['id']}/approve",
        json={"approver": "ops-manager", "comment": "approved"},
    )
    assert approved.status_code == 200
    assert "secret-token" not in approved.text

    timeline = await api_client.get(f"/api/incidents/{incident_id}/timeline")
    assert "secret-token" not in timeline.text
    assert any(item["event_type"] == "N8N_RESUME_FAILED" for item in timeline.json())


@pytest.mark.asyncio
async def test_sla_escalation_scan_is_idempotent_for_same_level(api_client, db_session):
    settings = get_settings()
    work_order = WorkOrder(
        work_order_no=await next_number(db_session, "work_order_no_seq", "WO"),
        incident_id=None,
        title="Overdue work order",
        description="SLA should escalate once per level",
        status=WorkOrderStatus.OPEN.value,
        priority=Severity.P1.value,
        creation_method=WorkOrderCreationMethod.API.value,
        sla_due_at=utcnow() - timedelta(minutes=20),
    )
    db_session.add(work_order)
    await db_session.commit()
    await db_session.refresh(work_order)

    first = await api_client.post(
        "/api/internal/sla/escalations/scan",
        headers={"X-Internal-Token": settings.internal_service_token},
        json={"level": 1},
    )
    second = await api_client.post(
        "/api/internal/sla/escalations/scan",
        headers={"X-Internal-Token": settings.internal_service_token},
        json={"level": 1},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created_notifications"] >= 1
    assert second.json()["created_notifications"] == 0

    notification_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.payload["work_order_id"].as_integer() == work_order.id,
                Notification.payload["sla_level"].as_integer() == 1,
            )
        )
    ).scalar_one()
    assert notification_count == 1


@pytest.mark.asyncio
async def test_close_case_creates_template_knowledge_case_without_llm_key(api_client, db_session, internal_token):
    incident = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "VISION-01",
            "incident_type": "stage4-close-case",
            "title": "Closure knowledge case",
            "description": "defect_rate=6.2%",
            "severity": "P2",
            "production_batch_no": "BATCH-20260714-001",
        },
    )
    incident_id = incident.json()["incident"]["id"]
    response = await api_client.post(
        "/api/internal/agent/close-case",
        headers={"X-Internal-Token": internal_token},
        json={"incident_id": incident_id, "resolution": "Adjusted camera calibration and verified sample output."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert "Closure knowledge case" in body["title"]

    case = await db_session.get(KnowledgeCase, body["id"])
    assert case is not None
    assert case.incident_id == incident_id
    assert "Adjusted camera calibration" in case.resolution


@pytest.mark.asyncio
async def test_rpa_contract_rejects_unknown_work_order_without_fake_success(api_client, db_session, internal_token):
    response = await api_client.post(
        "/api/internal/rpa/work-orders",
        headers={"X-Internal-Token": internal_token},
        json={"work_order_id": 12345, "reason": "MES API timeout"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "work_order_not_found"

    run_count = (await db_session.execute(select(func.count()).select_from(RpaRun))).scalar_one()
    assert run_count == 0


@pytest.mark.asyncio
async def test_internal_error_records_are_sanitized(api_client, db_session, internal_token):
    response = await api_client.post(
        "/api/internal/errors",
        headers={"X-Internal-Token": internal_token},
        json={
            "incident_id": None,
            "work_order_id": None,
            "error_code": "WORKFLOW_TEST",
            "error_message": "token=secret-value resume_url=http://n8n/resume/private",
        },
    )
    assert response.status_code == 200
    event = (await db_session.execute(select(WorkflowEvent).where(WorkflowEvent.event_type == "WORKFLOW_ERROR"))).scalar_one()
    assert "secret-value" not in str(event.payload)
    assert "resume/private" not in str(event.payload)
    assert "[REDACTED]" in str(event.payload)
