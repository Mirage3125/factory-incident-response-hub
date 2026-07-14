from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from factory_hub.config import get_settings
from factory_hub.domain.enums import IncidentStatus, Severity, WorkOrderStatus
from factory_hub.schemas import IncidentCreate, WorkOrderCreate
from factory_hub.services.core import (
    build_dedupe_key,
    calculate_sla_due,
    create_incident,
    create_work_order,
    decide_approval,
    register_approval,
    seed_demo_data,
    update_incident_status,
    update_work_order_status,
)
from factory_hub.domain.enums import ApprovalStatus
from factory_hub.domain.models import Equipment, Incident, KnowledgeCase, MaintenanceRecord, ProductionBatch, ProductionLine, WorkOrder
from sqlalchemy import func, select


def test_dedupe_key_is_stable():
    assert build_dedupe_key(1, " Vibration ", 3) == "1:vibration:3"
    assert build_dedupe_key(1, "Vibration", None) == "1:vibration:NO_BATCH"


def test_sla_uses_configured_minutes():
    base = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)
    assert calculate_sla_due(get_settings(), Severity.P1, base).minute == 15
    assert calculate_sla_due(get_settings(), Severity.P2, base).hour == 11


@pytest.mark.asyncio
async def test_duplicate_incident_updates_original_without_new_work_order(db_session):
    settings = get_settings()
    payload = IncidentCreate(
        equipment_code="CNC-01",
        incident_type="vibration",
        title="Vibration high",
        description="Spindle vibration exceeded threshold",
        severity=Severity.P1,
        production_batch_no="BATCH-20260714-001",
    )

    first, first_duplicate, _ = await create_incident(db_session, settings, payload)
    second, second_duplicate, original_id = await create_incident(db_session, settings, payload)

    assert first_duplicate is False
    assert second_duplicate is True
    assert second.id == first.id
    assert original_id == first.id
    assert second.occurrence_count == 2


@pytest.mark.asyncio
async def test_state_machine_blocks_illegal_transitions(db_session):
    incident, _, _ = await create_incident(
        db_session,
        get_settings(),
        IncidentCreate(
            equipment_code="CNC-01",
            incident_type="temperature",
            title="Temperature high",
            description="Temperature exceeded threshold",
            severity=Severity.P1,
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_incident_status(db_session, incident.id, IncidentStatus.CLOSED)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_work_order_numbers_are_unique(db_session):
    payload = WorkOrderCreate(title="Fix spindle", description="Inspect spindle", priority=Severity.P2)
    first = await create_work_order(db_session, get_settings(), payload)
    second = await create_work_order(db_session, get_settings(), payload)

    assert first.work_order_no != second.work_order_no
    assert first.work_order_no.startswith("WO-")


@pytest.mark.asyncio
async def test_work_order_state_machine_blocks_invalid_transition(db_session):
    work_order = await create_work_order(db_session, get_settings(), WorkOrderCreate(title="Fix", description="Fix issue", priority=Severity.P3))

    with pytest.raises(HTTPException):
        await update_work_order_status(db_session, work_order.id, WorkOrderStatus.CLOSED)


@pytest.mark.asyncio
async def test_duplicate_approval_is_rejected_and_decision_is_single_use(db_session):
    incident, _, _ = await create_incident(
        db_session,
        get_settings(),
        IncidentCreate(equipment_code="CNC-01", incident_type="approval", title="Needs approval", description="P1 approval", severity=Severity.P1),
    )
    approval = await register_approval(db_session, incident.id, "http://n8n/resume/secret")

    with pytest.raises(HTTPException):
        await register_approval(db_session, incident.id, "http://n8n/resume/secret2")

    await decide_approval(db_session, approval.id, ApprovalStatus.APPROVED, "supervisor", "ok")
    with pytest.raises(HTTPException):
        await decide_approval(db_session, approval.id, ApprovalStatus.REJECTED, "supervisor", "late")


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    await seed_demo_data(db_session, get_settings())

    counts = {
        "lines": (await db_session.execute(select(func.count()).select_from(ProductionLine))).scalar_one(),
        "equipment": (await db_session.execute(select(func.count()).select_from(Equipment))).scalar_one(),
        "batches": (await db_session.execute(select(func.count()).select_from(ProductionBatch))).scalar_one(),
        "maintenance": (await db_session.execute(select(func.count()).select_from(MaintenanceRecord))).scalar_one(),
        "incidents": (await db_session.execute(select(func.count()).select_from(Incident))).scalar_one(),
        "work_orders": (await db_session.execute(select(func.count()).select_from(WorkOrder))).scalar_one(),
        "cases": (await db_session.execute(select(func.count()).select_from(KnowledgeCase))).scalar_one(),
    }

    assert counts == {"lines": 2, "equipment": 5, "batches": 5, "maintenance": 10, "incidents": 10, "work_orders": 5, "cases": 2}
