from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from factory_hub.config import Settings
from factory_hub.agent.safety import sanitize_text
from factory_hub.domain.enums import ApprovalStatus, IncidentStatus, RpaStatus, Severity, WorkOrderCreationMethod, WorkOrderStatus
from factory_hub.domain.models import (
    Approval,
    Equipment,
    Incident,
    KnowledgeCase,
    MaintenanceRecord,
    Notification,
    ProductionBatch,
    ProductionLine,
    RpaRun,
    WorkflowEvent,
    WorkOrder,
)
from factory_hub.schemas import IncidentCreate, WorkOrderCreate


INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.RECEIVED: {IncidentStatus.ANALYZING, IncidentStatus.AWAITING_APPROVAL, IncidentStatus.WORK_ORDER_CREATED, IncidentStatus.REJECTED, IncidentStatus.WORKFLOW_FAILED},
    IncidentStatus.ANALYZING: {IncidentStatus.AWAITING_APPROVAL, IncidentStatus.WORK_ORDER_CREATED, IncidentStatus.REJECTED, IncidentStatus.WORKFLOW_FAILED},
    IncidentStatus.AWAITING_APPROVAL: {IncidentStatus.WORK_ORDER_CREATED, IncidentStatus.REJECTED, IncidentStatus.WORKFLOW_FAILED},
    IncidentStatus.WORK_ORDER_CREATED: {IncidentStatus.IN_PROGRESS, IncidentStatus.RESOLVED, IncidentStatus.WORKFLOW_FAILED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.RESOLVED, IncidentStatus.WORKFLOW_FAILED},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: set(),
    IncidentStatus.DUPLICATE: set(),
    IncidentStatus.REJECTED: set(),
    IncidentStatus.WORKFLOW_FAILED: {IncidentStatus.ANALYZING},
}

WORK_ORDER_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.OPEN: {WorkOrderStatus.ASSIGNED},
    WorkOrderStatus.ASSIGNED: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WAITING_PARTS, WorkOrderStatus.RESOLVED},
    WorkOrderStatus.IN_PROGRESS: {WorkOrderStatus.WAITING_PARTS, WorkOrderStatus.RESOLVED},
    WorkOrderStatus.WAITING_PARTS: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.RESOLVED},
    WorkOrderStatus.RESOLVED: {WorkOrderStatus.CLOSED},
    WorkOrderStatus.CLOSED: set(),
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def build_dedupe_key(equipment_id: int, incident_type: str, production_batch_id: int | None) -> str:
    batch_part = str(production_batch_id) if production_batch_id is not None else "NO_BATCH"
    return f"{equipment_id}:{incident_type.strip().lower()}:{batch_part}"


def calculate_sla_due(settings: Settings, severity: Severity, base_time: datetime | None = None) -> datetime:
    start = base_time or utcnow()
    minutes = settings.default_sla_minutes[severity.value]
    return start + timedelta(minutes=minutes)


async def next_number(session: AsyncSession, sequence: str, prefix: str) -> str:
    value = (await session.execute(text(f"SELECT nextval('{sequence}')"))).scalar_one()
    return f"{prefix}-{utcnow():%Y%m%d}-{value:04d}"


async def add_event(
    session: AsyncSession,
    event_type: str,
    *,
    incident_id: int | None = None,
    work_order_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> WorkflowEvent:
    event = WorkflowEvent(
        event_type=event_type,
        incident_id=incident_id,
        work_order_id=work_order_id,
        payload=payload or {},
    )
    session.add(event)
    return event


async def get_equipment_by_code(session: AsyncSession, code: str) -> Equipment:
    equipment = (await session.execute(select(Equipment).where(Equipment.code == code))).scalar_one_or_none()
    if equipment is None:
        raise HTTPException(status_code=404, detail="equipment_not_found")
    return equipment


async def get_batch_by_no(session: AsyncSession, batch_no: str | None) -> ProductionBatch | None:
    if not batch_no:
        return None
    batch = (await session.execute(select(ProductionBatch).where(ProductionBatch.batch_no == batch_no))).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="production_batch_not_found")
    return batch


async def list_equipment(session: AsyncSession) -> list[Equipment]:
    return list((await session.execute(select(Equipment).order_by(Equipment.code))).scalars().all())


async def get_equipment(session: AsyncSession, equipment_id: int) -> Equipment:
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail="equipment_not_found")
    return equipment


async def list_maintenance_records(session: AsyncSession, equipment_id: int) -> list[MaintenanceRecord]:
    await get_equipment(session, equipment_id)
    return list(
        (await session.execute(select(MaintenanceRecord).where(MaintenanceRecord.equipment_id == equipment_id).order_by(MaintenanceRecord.performed_at.desc())))
        .scalars()
        .all()
    )


async def create_incident(session: AsyncSession, settings: Settings, payload: IncidentCreate) -> tuple[Incident, bool, int | None]:
    equipment = await get_equipment_by_code(session, payload.equipment_code)
    batch = await get_batch_by_no(session, payload.production_batch_no)
    now = payload.occurred_at or utcnow()
    dedupe_key = build_dedupe_key(equipment.id, payload.incident_type, batch.id if batch else None)
    window_start = now - timedelta(minutes=settings.dedupe_window_minutes)
    existing = (
        await session.execute(
            select(Incident)
            .where(
                and_(
                    Incident.dedupe_key == dedupe_key,
                    Incident.last_seen_at >= window_start,
                    Incident.status.notin_([IncidentStatus.CLOSED.value, IncidentStatus.REJECTED.value]),
                )
            )
            .order_by(Incident.last_seen_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        existing.occurrence_count += 1
        existing.last_seen_at = now
        await add_event(session, "INCIDENT_DUPLICATED", incident_id=existing.id, payload={"dedupe_key": dedupe_key})
        await session.commit()
        await session.refresh(existing)
        return existing, True, existing.id

    incident = Incident(
        incident_no=await next_number(session, "incident_no_seq", "INC"),
        dedupe_key=dedupe_key,
        equipment_id=equipment.id,
        production_batch_id=batch.id if batch else None,
        incident_type=payload.incident_type,
        title=payload.title,
        description=payload.description,
        severity=payload.severity.value,
        status=IncidentStatus.RECEIVED.value,
        first_seen_at=now,
        last_seen_at=now,
        sla_due_at=calculate_sla_due(settings, payload.severity, now),
    )
    session.add(incident)
    await session.flush()
    await add_event(session, "INCIDENT_CREATED", incident_id=incident.id)
    await session.commit()
    await session.refresh(incident)
    return incident, False, None


async def list_incidents(session: AsyncSession) -> list[Incident]:
    return list((await session.execute(select(Incident).order_by(Incident.created_at.desc(), Incident.id.desc()))).scalars().all())


async def get_incident(session: AsyncSession, incident_id: int) -> Incident:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return incident


async def update_incident_status(session: AsyncSession, incident_id: int, target: IncidentStatus) -> Incident:
    incident = await get_incident(session, incident_id)
    current = IncidentStatus(incident.status)
    if target not in INCIDENT_TRANSITIONS[current]:
        raise HTTPException(status_code=409, detail=f"invalid_incident_transition:{current}->{target}")
    incident.status = target.value
    await add_event(session, "INCIDENT_STATUS_CHANGED", incident_id=incident.id, payload={"from": current.value, "to": target.value})
    await session.commit()
    await session.refresh(incident)
    return incident


async def incident_timeline(session: AsyncSession, incident_id: int) -> list[WorkflowEvent]:
    await get_incident(session, incident_id)
    return list((await session.execute(select(WorkflowEvent).where(WorkflowEvent.incident_id == incident_id).order_by(WorkflowEvent.created_at))).scalars().all())


async def create_work_order(session: AsyncSession, settings: Settings, payload: WorkOrderCreate) -> WorkOrder:
    if payload.incident_id is not None:
        await get_incident(session, payload.incident_id)
    work_order = WorkOrder(
        work_order_no=await next_number(session, "work_order_no_seq", "WO"),
        incident_id=payload.incident_id,
        title=payload.title,
        description=payload.description,
        status=WorkOrderStatus.OPEN.value,
        priority=payload.priority.value,
        assigned_team=payload.assigned_team,
        assignee=payload.assignee,
        creation_method=payload.creation_method.value,
        sla_due_at=calculate_sla_due(settings, payload.priority),
    )
    session.add(work_order)
    await session.flush()
    await add_event(session, "WORK_ORDER_CREATED", incident_id=payload.incident_id, work_order_id=work_order.id)
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def list_work_orders(session: AsyncSession) -> list[WorkOrder]:
    return list((await session.execute(select(WorkOrder).order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc()))).scalars().all())


async def get_work_order(session: AsyncSession, work_order_id: int) -> WorkOrder:
    work_order = await session.get(WorkOrder, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404, detail="work_order_not_found")
    return work_order


async def assign_work_order(session: AsyncSession, work_order_id: int, assigned_team: str, assignee: str | None) -> WorkOrder:
    work_order = await get_work_order(session, work_order_id)
    work_order.assigned_team = assigned_team
    work_order.assignee = assignee
    if WorkOrderStatus(work_order.status) == WorkOrderStatus.OPEN:
        work_order.status = WorkOrderStatus.ASSIGNED.value
    await add_event(session, "WORK_ORDER_ASSIGNED", incident_id=work_order.incident_id, work_order_id=work_order.id)
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def update_work_order_status(session: AsyncSession, work_order_id: int, target: WorkOrderStatus) -> WorkOrder:
    work_order = await get_work_order(session, work_order_id)
    current = WorkOrderStatus(work_order.status)
    if target not in WORK_ORDER_TRANSITIONS[current]:
        raise HTTPException(status_code=409, detail=f"invalid_work_order_transition:{current}->{target}")
    work_order.status = target.value
    if target == WorkOrderStatus.RESOLVED:
        work_order.resolved_at = utcnow()
    await add_event(session, "WORK_ORDER_STATUS_CHANGED", incident_id=work_order.incident_id, work_order_id=work_order.id, payload={"from": current.value, "to": target.value})
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def resolve_work_order(session: AsyncSession, work_order_id: int, resolution: str) -> WorkOrder:
    work_order = await update_work_order_status(session, work_order_id, WorkOrderStatus.RESOLVED)
    await add_event(session, "WORK_ORDER_RESOLVED", incident_id=work_order.incident_id, work_order_id=work_order.id, payload={"resolution": resolution})
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def pending_approvals(session: AsyncSession) -> list[Approval]:
    return list((await session.execute(select(Approval).where(Approval.status == ApprovalStatus.PENDING.value).order_by(Approval.created_at))).scalars().all())


async def register_approval(session: AsyncSession, incident_id: int, resume_url: str) -> Approval:
    await get_incident(session, incident_id)
    existing = (
        await session.execute(select(Approval).where(Approval.incident_id == incident_id, Approval.status == ApprovalStatus.PENDING.value))
    ).scalar_one_or_none()
    if existing:
        if existing.resume_url and existing.resume_url != resume_url:
            raise HTTPException(status_code=409, detail="approval_already_pending")
        existing.resume_url = resume_url
        await add_event(session, "APPROVAL_RESUME_REGISTERED", incident_id=incident_id)
        await session.commit()
        await session.refresh(existing)
        return existing
    approval = Approval(incident_id=incident_id, status=ApprovalStatus.PENDING.value, resume_url=resume_url)
    session.add(approval)
    await add_event(session, "APPROVAL_REGISTERED", incident_id=incident_id)
    await session.commit()
    await session.refresh(approval)
    return approval


async def decide_approval(session: AsyncSession, approval_id: int, status: ApprovalStatus, approver: str, comment: str | None) -> Approval:
    approval = await session.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval_not_found")
    if approval.status != ApprovalStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="approval_already_decided")
    approval.status = status.value
    approval.approver = approver
    approval.comment = comment
    approval.decided_at = utcnow()
    await add_event(session, f"APPROVAL_{status.value}", incident_id=approval.incident_id)
    await session.commit()
    await session.refresh(approval)
    return approval


async def dashboard_summary(session: AsyncSession) -> dict[str, int]:
    total_incidents = (await session.execute(select(func.count()).select_from(Incident))).scalar_one()
    open_incidents = (
        await session.execute(select(func.count()).select_from(Incident).where(Incident.status.notin_([IncidentStatus.CLOSED.value, IncidentStatus.REJECTED.value])))
    ).scalar_one()
    total_work_orders = (await session.execute(select(func.count()).select_from(WorkOrder))).scalar_one()
    pending = (await session.execute(select(func.count()).select_from(Approval).where(Approval.status == ApprovalStatus.PENDING.value))).scalar_one()
    return {
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "total_work_orders": total_work_orders,
        "pending_approvals": pending,
    }


async def severity_distribution(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.execute(select(Incident.severity, func.count()).group_by(Incident.severity))).all()
    return [{"severity": severity, "count": count} for severity, count in rows]


async def recent_incidents(session: AsyncSession, limit: int = 10) -> list[Incident]:
    return list((await session.execute(select(Incident).order_by(Incident.created_at.desc(), Incident.id.desc()).limit(limit))).scalars().all())


async def sla_metrics(session: AsyncSession) -> dict[str, int]:
    now = utcnow()
    due_soon = now + timedelta(minutes=30)
    overdue_work_orders = (
        await session.execute(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.sla_due_at < now, WorkOrder.status.notin_([WorkOrderStatus.RESOLVED.value, WorkOrderStatus.CLOSED.value]))
        )
    ).scalar_one()
    due_soon_work_orders = (
        await session.execute(
            select(func.count()).select_from(WorkOrder).where(
                WorkOrder.sla_due_at >= now,
                WorkOrder.sla_due_at <= due_soon,
                WorkOrder.status.notin_([WorkOrderStatus.RESOLVED.value, WorkOrderStatus.CLOSED.value]),
            )
        )
    ).scalar_one()
    overdue_incidents = (
        await session.execute(
            select(func.count()).select_from(Incident).where(Incident.sla_due_at < now, Incident.status.notin_([IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value]))
        )
    ).scalar_one()
    return {"overdue_work_orders": overdue_work_orders, "due_soon_work_orders": due_soon_work_orders, "overdue_incidents": overdue_incidents}


async def create_workflow_event(session: AsyncSession, event_type: str, incident_id: int | None, work_order_id: int | None, payload: dict[str, Any]) -> WorkflowEvent:
    event = await add_event(session, event_type, incident_id=incident_id, work_order_id=work_order_id, payload=payload)
    await session.commit()
    await session.refresh(event)
    return event


async def create_notification(session: AsyncSession, target: str, message: str, status: str, payload: dict[str, Any]) -> Notification:
    notification = Notification(target=target, message=message, status=status, payload=payload)
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def create_rpa_run(session: AsyncSession, payload: dict[str, Any]) -> RpaRun:
    run = RpaRun(**payload)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def list_rpa_runs(session: AsyncSession, work_order_id: int | None = None) -> list[RpaRun]:
    query = select(RpaRun).order_by(RpaRun.created_at.desc(), RpaRun.id.desc())
    if work_order_id is not None:
        query = query.where(RpaRun.work_order_id == work_order_id)
    return list((await session.execute(query)).scalars().all())


async def record_error(session: AsyncSession, incident_id: int | None, work_order_id: int | None, error_code: str, error_message: str) -> WorkflowEvent:
    return await create_workflow_event(
        session,
        "WORKFLOW_ERROR",
        incident_id,
        work_order_id,
        {"error_code": error_code, "error_message": sanitize_text(error_message)},
    )


DEMO_SCENARIOS = [
    {"code": "cnc-vibration-p1", "name": "CNC spindle vibration risk", "equipment_code": "CNC-01", "incident_type": "vibration", "severity": Severity.P1},
    {"code": "vision-defect-p2", "name": "Vision defect rate increase", "equipment_code": "VISION-01", "incident_type": "defect_rate", "severity": Severity.P2},
]


async def trigger_demo_scenario(session: AsyncSession, settings: Settings, code: str) -> tuple[Incident, bool, int | None]:
    scenario = next((item for item in DEMO_SCENARIOS if item["code"] == code), None)
    if scenario is None:
        raise HTTPException(status_code=404, detail="demo_scenario_not_found")
    payload = IncidentCreate(
        equipment_code=scenario["equipment_code"],
        incident_type=scenario["incident_type"],
        title=scenario["name"],
        description=f"Demo trigger for {scenario['name']}",
        severity=scenario["severity"],
        production_batch_no="BATCH-20260714-001",
    )
    return await create_incident(session, settings, payload)


async def seed_demo_data(session: AsyncSession, settings: Settings) -> None:
    now = utcnow()
    lines = [("LINE-A", "Assembly Line A"), ("LINE-B", "Assembly Line B")]
    for code, name in lines:
        if not (await session.execute(select(ProductionLine).where(ProductionLine.code == code))).scalar_one_or_none():
            session.add(ProductionLine(code=code, name=name))

    equipment_rows = [
        ("CNC-01", "Main spindle CNC", "LINE-A", "Workshop A", "critical"),
        ("CNC-02", "Secondary CNC", "LINE-A", "Workshop A", "normal"),
        ("VISION-01", "Vision inspection", "LINE-B", "Quality station", "critical"),
        ("PRESS-01", "Hydraulic press", "LINE-B", "Workshop B", "critical"),
        ("ROBOT-01", "Handling robot", "LINE-A", "Cell 3", "normal"),
    ]
    for code, name, line_code, location, criticality in equipment_rows:
        if not (await session.execute(select(Equipment).where(Equipment.code == code))).scalar_one_or_none():
            session.add(Equipment(code=code, name=name, line_code=line_code, location=location, criticality=criticality))
    await session.flush()

    for index in range(1, 6):
        batch_no = f"BATCH-20260714-{index:03d}"
        if not (await session.execute(select(ProductionBatch).where(ProductionBatch.batch_no == batch_no))).scalar_one_or_none():
            session.add(
                ProductionBatch(
                    batch_no=batch_no,
                    product_code=f"PROD-{index:02d}",
                    line_code="LINE-A" if index % 2 else "LINE-B",
                    started_at=now - timedelta(hours=index),
                )
            )
    await session.flush()

    equipment = list((await session.execute(select(Equipment).order_by(Equipment.code))).scalars().all())
    for item in equipment:
        count = (await session.execute(select(func.count()).select_from(MaintenanceRecord).where(MaintenanceRecord.equipment_id == item.id))).scalar_one()
        for offset in range(count + 1, 3):
            session.add(
                MaintenanceRecord(
                    equipment_id=item.id,
                    performed_at=now - timedelta(days=offset * 7),
                    summary=f"Routine maintenance {offset} for {item.code}",
                    technician=f"tech-{offset}",
                )
            )
    await session.flush()

    existing_incidents = (await session.execute(select(func.count()).select_from(Incident))).scalar_one()
    batches = list((await session.execute(select(ProductionBatch).order_by(ProductionBatch.batch_no))).scalars().all())
    for index in range(existing_incidents + 1, 11):
        eq = equipment[(index - 1) % len(equipment)]
        batch = batches[(index - 1) % len(batches)]
        severity = list(Severity)[(index - 1) % 4]
        created_at = now - timedelta(hours=index)
        incident = Incident(
            incident_no=await next_number(session, "incident_no_seq", "INC"),
            dedupe_key=build_dedupe_key(eq.id, f"historical-{index}", batch.id),
            equipment_id=eq.id,
            production_batch_id=batch.id,
            incident_type=f"historical-{index}",
            title=f"Historical incident {index}",
            description=f"Seeded historical incident {index}",
            severity=severity.value,
            status=IncidentStatus.CLOSED.value if index <= 5 else IncidentStatus.RECEIVED.value,
            first_seen_at=created_at,
            last_seen_at=created_at,
            sla_due_at=calculate_sla_due(settings, severity, created_at),
        )
        session.add(incident)
    await session.flush()

    incidents = list((await session.execute(select(Incident).order_by(Incident.id).limit(5))).scalars().all())
    existing_work_orders = (await session.execute(select(func.count()).select_from(WorkOrder))).scalar_one()
    for index in range(existing_work_orders + 1, 6):
        incident = incidents[(index - 1) % len(incidents)]
        session.add(
            WorkOrder(
                work_order_no=await next_number(session, "work_order_no_seq", "WO"),
                incident_id=incident.id,
                title=f"Historical work order {index}",
                description=f"Seeded work order {index}",
                status=WorkOrderStatus.CLOSED.value if index <= 2 else WorkOrderStatus.OPEN.value,
                priority=incident.severity,
                creation_method=WorkOrderCreationMethod.API.value,
                sla_due_at=incident.sla_due_at,
                resolved_at=now - timedelta(hours=1) if index <= 2 else None,
            )
        )

    existing_cases = (await session.execute(select(func.count()).select_from(KnowledgeCase))).scalar_one()
    for index in range(existing_cases + 1, 3):
        session.add(KnowledgeCase(title=f"Knowledge case {index}", summary=f"Case summary {index}", resolution=f"Resolution steps {index}"))
    await session.commit()
