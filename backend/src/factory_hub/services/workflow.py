from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factory_hub.agent.safety import sanitize_payload, sanitize_text
from factory_hub.config import Settings
from factory_hub.domain.enums import ApprovalStatus, IncidentStatus, RpaStatus, WorkOrderCreationMethod, WorkOrderStatus
from factory_hub.domain.models import Approval, Incident, KnowledgeCase, Notification, RpaRun, WorkOrder
from factory_hub.services.core import add_event, utcnow


async def resume_n8n_approval(
    session: AsyncSession,
    settings: Settings,
    approval: Approval,
    status: ApprovalStatus,
    approver: str,
    comment: str | None,
) -> None:
    if not approval.resume_url:
        await add_event(session, "N8N_RESUME_SKIPPED", incident_id=approval.incident_id, payload={"reason": "missing_resume_url"})
        return

    body = {"approval_id": approval.id, "incident_id": approval.incident_id, "status": status.value, "approver": approver, "comment": comment}
    try:
        async with httpx.AsyncClient(timeout=settings.n8n_resume_timeout) as client:
            response = await client.post(approval.resume_url, json=body)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {404, 405}:
                    raise
                response = await client.get(approval.resume_url, params=body)
                response.raise_for_status()
    except Exception as exc:
        payload = sanitize_payload({"error": exc.__class__.__name__, "message": "n8n resume request failed"})
        await add_event(session, "N8N_RESUME_FAILED", incident_id=approval.incident_id, payload=payload)
        session.add(
            Notification(
                target="workflow-admin",
                message=f"n8n approval resume failed for approval {approval.id}",
                status="QUEUED",
                payload={"approval_id": approval.id, "incident_id": approval.incident_id},
            )
        )
        return

    await add_event(session, "N8N_RESUMED", incident_id=approval.incident_id, payload={"approval_id": approval.id})


async def scan_sla_escalations(session: AsyncSession, level: int) -> dict[str, int]:
    now = utcnow()
    rows = (
        await session.execute(
            select(WorkOrder).where(
                WorkOrder.sla_due_at < now,
                WorkOrder.status.notin_([WorkOrderStatus.RESOLVED.value, WorkOrderStatus.CLOSED.value]),
            )
        )
    ).scalars().all()
    created = 0
    for work_order in rows:
        existing = (
            await session.execute(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.payload["work_order_id"].as_integer() == work_order.id,
                    Notification.payload["sla_level"].as_integer() == level,
                )
            )
        ).scalar_one()
        if existing:
            continue
        session.add(
            Notification(
                target="maintenance-supervisor",
                message=f"SLA level {level} escalation for {work_order.work_order_no}",
                status="QUEUED",
                payload={"work_order_id": work_order.id, "work_order_no": work_order.work_order_no, "sla_level": level},
            )
        )
        await add_event(session, "SLA_ESCALATED", incident_id=work_order.incident_id, work_order_id=work_order.id, payload={"sla_level": level})
        created += 1
    await session.commit()
    return {"scanned_work_orders": len(rows), "created_notifications": created}


async def close_incident_case(session: AsyncSession, incident_id: int, resolution: str) -> KnowledgeCase:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    existing = (await session.execute(select(KnowledgeCase).where(KnowledgeCase.incident_id == incident_id))).scalar_one_or_none()
    if existing:
        return existing
    summary = f"Template closure summary for {incident.incident_no}: {sanitize_text(incident.title, 160)}"
    case = KnowledgeCase(
        incident_id=incident.id,
        title=f"Knowledge case for {incident.title}",
        summary=summary,
        resolution=sanitize_text(resolution, 4000),
    )
    session.add(case)
    if incident.status in {IncidentStatus.RESOLVED.value, IncidentStatus.IN_PROGRESS.value, IncidentStatus.WORK_ORDER_CREATED.value}:
        incident.status = IncidentStatus.CLOSED.value if incident.status == IncidentStatus.RESOLVED.value else IncidentStatus.RESOLVED.value
    await add_event(session, "KNOWLEDGE_CASE_CREATED", incident_id=incident.id)
    await session.commit()
    await session.refresh(case)
    return case


async def record_rpa_not_implemented(session: AsyncSession, work_order_id: int | None, reason: str) -> dict[str, Any]:
    linked_work_order_id = work_order_id
    if work_order_id is not None and await session.get(WorkOrder, work_order_id) is None:
        linked_work_order_id = None

    run = RpaRun(
        work_order_id=linked_work_order_id,
        status=RpaStatus.FAILED.value,
        external_id=None,
        steps=[{"step": "rpa_worker_contract", "status": "not_implemented"}],
        error_code="RPA_NOT_IMPLEMENTED",
        error_message=sanitize_text(reason, 500),
    )
    session.add(run)
    await session.commit()
    return {"success": False, "external_id": None, "error_code": "RPA_NOT_IMPLEMENTED", "error_message": "RPA worker is not implemented in stage 4"}


async def apply_external_work_order_result(
    session: AsyncSession,
    work_order_id: int,
    external_id: str,
    creation_method: WorkOrderCreationMethod,
) -> WorkOrder:
    work_order = (
        await session.execute(
            select(WorkOrder)
            .options(selectinload(WorkOrder.incident).selectinload(Incident.equipment))
            .where(WorkOrder.id == work_order_id)
        )
    ).scalar_one_or_none()
    if work_order is None:
        raise HTTPException(status_code=404, detail="work_order_not_found")
    work_order.external_id = sanitize_text(external_id, 120)
    work_order.creation_method = creation_method.value
    await add_event(
        session,
        "EXTERNAL_WORK_ORDER_LINKED",
        incident_id=work_order.incident_id,
        work_order_id=work_order.id,
        payload={"external_id": work_order.external_id, "creation_method": work_order.creation_method},
    )
    await session.commit()
    await session.refresh(work_order)
    return work_order


async def create_work_order_with_rpa(session: AsyncSession, settings: Settings, work_order_id: int, reason: str) -> dict[str, Any]:
    work_order = (
        await session.execute(
            select(WorkOrder)
            .options(selectinload(WorkOrder.incident).selectinload(Incident.equipment))
            .where(WorkOrder.id == work_order_id)
        )
    ).scalar_one_or_none()
    if work_order is None:
        raise HTTPException(status_code=404, detail="work_order_not_found")

    payload = {
        "work_order_id": work_order.id,
        "incident_no": work_order.incident.incident_no if work_order.incident else work_order.work_order_no,
        "equipment_code": work_order.incident.equipment.code if work_order.incident and work_order.incident.equipment else "UNKNOWN",
        "title": work_order.title,
        "priority": work_order.priority,
        "description": work_order.description,
        "assigned_team": work_order.assigned_team or "maintenance",
        "reason": sanitize_text(reason, 500),
    }
    try:
        async with httpx.AsyncClient(timeout=settings.rpa_worker_timeout) as client:
            response = await client.post(
                f"{settings.rpa_worker_url.rstrip('/')}/internal/rpa/work-orders",
                headers={"X-Internal-Token": settings.internal_service_token},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except Exception as exc:
        body = {
            "success": False,
            "external_id": None,
            "screenshot_path": None,
            "steps": [{"step": "call_rpa_worker", "status": "failed"}],
            "error_code": "RPA_WORKER_UNAVAILABLE",
            "error_message": sanitize_text(f"{exc.__class__.__name__}: RPA worker request failed", 500),
        }

    success = bool(body.get("success"))
    error_message = sanitize_text(body.get("error_message") or "", 500) or None
    run = RpaRun(
        work_order_id=work_order.id,
        status=RpaStatus.SUCCEEDED.value if success else RpaStatus.FAILED.value,
        external_id=sanitize_text(body.get("external_id"), 120) if body.get("external_id") else None,
        screenshot_path=sanitize_text(body.get("screenshot_path"), 500) if body.get("screenshot_path") else None,
        steps=sanitize_payload(body.get("steps") or []),
        error_code=sanitize_text(body.get("error_code"), 80) if body.get("error_code") else None,
        error_message=error_message,
    )
    session.add(run)
    if success and run.external_id:
        work_order.external_id = run.external_id
        work_order.creation_method = WorkOrderCreationMethod.RPA.value
        await add_event(
            session,
            "RPA_WORK_ORDER_CREATED",
            incident_id=work_order.incident_id,
            work_order_id=work_order.id,
            payload={"external_id": run.external_id, "screenshot_path": run.screenshot_path},
        )
        await session.commit()
        return {
            "success": True,
            "external_id": run.external_id,
            "screenshot_path": run.screenshot_path,
            "steps": run.steps,
            "error_code": None,
            "error_message": None,
        }

    await add_event(
        session,
        "RPA_WORK_ORDER_FAILED",
        incident_id=work_order.incident_id,
        work_order_id=work_order.id,
        payload={"error_code": run.error_code, "error_message": run.error_message},
    )
    await session.commit()
    return {
        "success": False,
        "external_id": None,
        "screenshot_path": run.screenshot_path,
        "steps": run.steps,
        "error_code": run.error_code or "RPA_FAILED",
        "error_message": run.error_message or "RPA worker failed",
    }
