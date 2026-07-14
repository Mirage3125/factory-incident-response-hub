from urllib.parse import urlsplit, urlunsplit

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factory_hub.api.dependencies import require_internal_token
from factory_hub.agent.schemas import AnalysisRequest, IncidentAnalysisRead, InternalAnalysisRequest
from factory_hub.agent.service import analysis_read_from_run, analyze_incident
from factory_hub.config import Settings, get_settings
from factory_hub.database import get_session
from factory_hub.schemas import (
    ApprovalDecision,
    ApprovalRead,
    ApprovalRegister,
    CloseCaseRequest,
    DashboardSummary,
    DemoRpaFallbackResponse,
    DemoScenarioRead,
    EquipmentRead,
    ErrorRecordCreate,
    ExternalWorkOrderResult,
    IdResponse,
    IncidentCreate,
    IncidentCreateResponse,
    IncidentRead,
    IncidentStatusUpdate,
    KnowledgeCaseRead,
    MaintenanceRecordRead,
    NotificationCreate,
    RpaWorkOrderRequest,
    RpaWorkOrderResponse,
    RpaRunCreate,
    RpaRunRead,
    SeverityBucket,
    SlaEscalationScanRequest,
    SlaEscalationScanResponse,
    SlaMetrics,
    WorkflowEventCreate,
    WorkOrderAssign,
    WorkOrderCreate,
    WorkOrderRead,
    WorkOrderResolve,
    WorkOrderStatusUpdate,
)
from factory_hub.services import core
from factory_hub.services import workflow
from factory_hub.domain.enums import ApprovalStatus
from factory_hub.domain.models import IncidentAnalysisRun, RpaRun


router = APIRouter(prefix="/api")
internal_router = APIRouter(prefix="/api/internal", dependencies=[Depends(require_internal_token)])


def _normalize_n8n_resume_url(resume_url: str, settings: Settings) -> str:
    parsed = urlsplit(resume_url)
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return resume_url
    internal = urlsplit(settings.n8n_base_url)
    return urlunsplit((internal.scheme, internal.netloc, parsed.path, parsed.query, parsed.fragment))


@router.get("/equipment", response_model=list[EquipmentRead])
async def equipment_list(session: AsyncSession = Depends(get_session)) -> list:
    return await core.list_equipment(session)


@router.get("/equipment/{equipment_id}", response_model=EquipmentRead)
async def equipment_detail(equipment_id: int, session: AsyncSession = Depends(get_session)):
    return await core.get_equipment(session, equipment_id)


@router.get("/equipment/{equipment_id}/maintenance-records", response_model=list[MaintenanceRecordRead])
async def equipment_maintenance(equipment_id: int, session: AsyncSession = Depends(get_session)) -> list:
    return await core.list_maintenance_records(session, equipment_id)


@router.post("/incidents", response_model=IncidentCreateResponse, status_code=status.HTTP_201_CREATED)
async def incident_create(
    payload: IncidentCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> IncidentCreateResponse:
    incident, duplicate, original_id = await core.create_incident(session, settings, payload)
    return IncidentCreateResponse(incident=IncidentRead.model_validate(incident), duplicate=duplicate, original_incident_id=original_id)


@router.get("/incidents", response_model=list[IncidentRead])
async def incident_list(session: AsyncSession = Depends(get_session)) -> list:
    return await core.list_incidents(session)


@router.get("/incidents/{incident_id}", response_model=IncidentRead)
async def incident_detail(incident_id: int, session: AsyncSession = Depends(get_session)):
    return await core.get_incident(session, incident_id)


@router.get("/incidents/{incident_id}/timeline")
async def incident_timeline(incident_id: int, session: AsyncSession = Depends(get_session)) -> list[dict]:
    events = await core.incident_timeline(session, incident_id)
    return [
        {
            "id": event.id,
            "event_type": event.event_type,
            "payload": event.payload,
            "created_at": event.created_at,
            "work_order_id": event.work_order_id,
        }
        for event in events
    ]


@router.patch("/incidents/{incident_id}/status", response_model=IncidentRead)
async def incident_status(incident_id: int, payload: IncidentStatusUpdate, session: AsyncSession = Depends(get_session)):
    return await core.update_incident_status(session, incident_id, payload.status)


@router.post("/incidents/{incident_id}/analyze", response_model=IncidentAnalysisRead)
async def incident_analyze(
    incident_id: int,
    payload: AnalysisRequest | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    request = payload or AnalysisRequest()
    return await analyze_incident(session, settings, incident_id, force=request.force)


@router.get("/incidents/{incident_id}/analysis-runs", response_model=list[IncidentAnalysisRead])
async def incident_analysis_runs(incident_id: int, session: AsyncSession = Depends(get_session)):
    await core.get_incident(session, incident_id)
    runs = (
        await session.execute(
            select(IncidentAnalysisRun)
            .where(IncidentAnalysisRun.incident_id == incident_id)
            .order_by(IncidentAnalysisRun.created_at.desc(), IncidentAnalysisRun.id.desc())
        )
    ).scalars().all()
    return [analysis_read_from_run(run) for run in runs]


@router.post("/work-orders", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
async def work_order_create(
    payload: WorkOrderCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await core.create_work_order(session, settings, payload)


@router.get("/work-orders", response_model=list[WorkOrderRead])
async def work_order_list(session: AsyncSession = Depends(get_session)) -> list:
    return await core.list_work_orders(session)


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderRead)
async def work_order_detail(work_order_id: int, session: AsyncSession = Depends(get_session)):
    return await core.get_work_order(session, work_order_id)


@router.patch("/work-orders/{work_order_id}/status", response_model=WorkOrderRead)
async def work_order_status(work_order_id: int, payload: WorkOrderStatusUpdate, session: AsyncSession = Depends(get_session)):
    return await core.update_work_order_status(session, work_order_id, payload.status)


@router.post("/work-orders/{work_order_id}/assign", response_model=WorkOrderRead)
async def work_order_assign(work_order_id: int, payload: WorkOrderAssign, session: AsyncSession = Depends(get_session)):
    return await core.assign_work_order(session, work_order_id, payload.assigned_team, payload.assignee)


@router.post("/work-orders/{work_order_id}/resolve", response_model=WorkOrderRead)
async def work_order_resolve(work_order_id: int, payload: WorkOrderResolve, session: AsyncSession = Depends(get_session)):
    return await core.resolve_work_order(session, work_order_id, payload.resolution)


@router.get("/approvals/pending", response_model=list[ApprovalRead])
async def approval_pending(session: AsyncSession = Depends(get_session)) -> list:
    return await core.pending_approvals(session)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRead)
async def approval_approve(
    approval_id: int,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    approval = await core.decide_approval(session, approval_id, ApprovalStatus.APPROVED, payload.approver, payload.comment)
    await workflow.resume_n8n_approval(session, settings, approval, ApprovalStatus.APPROVED, payload.approver, payload.comment)
    await session.commit()
    await session.refresh(approval)
    return approval


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRead)
async def approval_reject(
    approval_id: int,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    approval = await core.decide_approval(session, approval_id, ApprovalStatus.REJECTED, payload.approver, payload.comment)
    await workflow.resume_n8n_approval(session, settings, approval, ApprovalStatus.REJECTED, payload.approver, payload.comment)
    await session.commit()
    await session.refresh(approval)
    return approval


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(session: AsyncSession = Depends(get_session)):
    return await core.dashboard_summary(session)


@router.get("/dashboard/severity-distribution", response_model=list[SeverityBucket])
async def dashboard_severity_distribution(session: AsyncSession = Depends(get_session)):
    return await core.severity_distribution(session)


@router.get("/dashboard/recent-incidents", response_model=list[IncidentRead])
async def dashboard_recent_incidents(session: AsyncSession = Depends(get_session)):
    return await core.recent_incidents(session)


@router.get("/dashboard/sla-metrics", response_model=SlaMetrics)
async def dashboard_sla_metrics(session: AsyncSession = Depends(get_session)):
    return await core.sla_metrics(session)


@router.get("/demo/scenarios", response_model=list[DemoScenarioRead])
async def demo_scenarios():
    return core.DEMO_SCENARIOS


@router.post("/demo/scenarios/{scenario_code}/trigger", response_model=IncidentCreateResponse)
async def demo_trigger(
    scenario_code: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    incident, duplicate, original_id = await core.trigger_demo_scenario(session, settings, scenario_code)
    return IncidentCreateResponse(incident=IncidentRead.model_validate(incident), duplicate=duplicate, original_incident_id=original_id)


@router.post("/demo/rpa-fallback", response_model=DemoRpaFallbackResponse)
async def demo_rpa_fallback(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    incident_payload = IncidentCreate(
        equipment_code="CNC-01",
        incident_type=f"mes_api_failure_rpa_{core.utcnow():%Y%m%d%H%M%S%f}",
        title="MES API technical failure with RPA fallback",
        description="Demo scenario: MES API returns a technical failure and the system falls back to Playwright RPA.",
        severity="P2",
        production_batch_no="BATCH-20260714-001",
    )
    incident, _, _ = await core.create_incident(session, settings, incident_payload)
    work_order = await core.create_work_order(
        session,
        settings,
        WorkOrderCreate(
            incident_id=incident.id,
            title=f"Fallback MES entry for {incident.incident_no}",
            description="Create external work order after simulated MES API 503.",
            priority="P2",
            assigned_team="maintenance",
        ),
    )
    await core.create_workflow_event(
        session,
        "MES_API_TECHNICAL_FAILURE",
        incident.id,
        work_order.id,
        {"status_code": 503, "demo": True},
    )
    rpa_body = await workflow.create_work_order_with_rpa(session, settings, work_order.id, "Demo MES API 503 fallback")
    refreshed_work_order = await core.get_work_order(session, work_order.id)
    runs = await core.list_rpa_runs(session, work_order_id=work_order.id)
    return DemoRpaFallbackResponse(
        incident=IncidentRead.model_validate(incident),
        work_order=WorkOrderRead.model_validate(refreshed_work_order),
        rpa_run=RpaRunRead.model_validate(runs[0]) if runs else None,
        rpa_result=RpaWorkOrderResponse.model_validate(rpa_body),
    )


@router.get("/rpa-runs", response_model=list[RpaRunRead])
async def rpa_run_list(work_order_id: int | None = None, session: AsyncSession = Depends(get_session)) -> list:
    return await core.list_rpa_runs(session, work_order_id)


@router.get("/rpa-runs/{run_id}", response_model=RpaRunRead)
async def rpa_run_detail(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await session.get(RpaRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="rpa_run_not_found")
    return run


@internal_router.post("/workflow-events", response_model=IdResponse)
async def internal_workflow_event(payload: WorkflowEventCreate, session: AsyncSession = Depends(get_session)):
    event = await core.create_workflow_event(session, payload.event_type, payload.incident_id, payload.work_order_id, payload.payload)
    return IdResponse(id=event.id)


@internal_router.post("/notifications", response_model=IdResponse)
async def internal_notification(payload: NotificationCreate, session: AsyncSession = Depends(get_session)):
    notification = await core.create_notification(session, payload.target, payload.message, payload.status, payload.payload)
    return IdResponse(id=notification.id)


@internal_router.post("/work-orders/create", response_model=WorkOrderRead)
async def internal_work_order_create(
    payload: WorkOrderCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await core.create_work_order(session, settings, payload)


@internal_router.post("/approvals/register", response_model=ApprovalRead)
async def internal_approval_register(
    payload: ApprovalRegister,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    resume_url = _normalize_n8n_resume_url(payload.resume_url, settings)
    return await core.register_approval(session, payload.incident_id, resume_url)


@internal_router.post("/rpa-runs", response_model=IdResponse)
async def internal_rpa_run(payload: RpaRunCreate, session: AsyncSession = Depends(get_session)):
    run = await core.create_rpa_run(session, payload.model_dump())
    return IdResponse(id=run.id)


@internal_router.post("/work-orders/external-result", response_model=WorkOrderRead)
async def internal_work_order_external_result(payload: ExternalWorkOrderResult, session: AsyncSession = Depends(get_session)):
    return await workflow.apply_external_work_order_result(session, payload.work_order_id, payload.external_id, payload.creation_method)


@internal_router.post("/errors", response_model=IdResponse)
async def internal_error(payload: ErrorRecordCreate, session: AsyncSession = Depends(get_session)):
    event = await core.record_error(session, payload.incident_id, payload.work_order_id, payload.error_code, payload.error_message)
    return IdResponse(id=event.id)


@internal_router.post("/agent/analyze", response_model=IncidentAnalysisRead)
async def internal_agent_analyze(
    payload: InternalAnalysisRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await analyze_incident(session, settings, payload.incident_id, force=payload.force)


@internal_router.post("/agent/close-case", response_model=KnowledgeCaseRead)
async def internal_agent_close_case(payload: CloseCaseRequest, session: AsyncSession = Depends(get_session)):
    return await workflow.close_incident_case(session, payload.incident_id, payload.resolution)


@internal_router.post("/sla/escalations/scan", response_model=SlaEscalationScanResponse)
async def internal_sla_escalation_scan(payload: SlaEscalationScanRequest, session: AsyncSession = Depends(get_session)):
    return await workflow.scan_sla_escalations(session, payload.level)


@internal_router.post("/rpa/work-orders", response_model=RpaWorkOrderResponse)
async def internal_rpa_work_order(
    payload: RpaWorkOrderRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    body = await workflow.create_work_order_with_rpa(session, settings, payload.work_order_id, payload.reason)
    if not body["success"]:
        raise HTTPException(status_code=502, detail=body)
    return body


@router.get("/rpa-runs/{run_id}/screenshot")
async def rpa_run_screenshot(run_id: int, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    run = (await session.execute(select(RpaRun).where(RpaRun.id == run_id))).scalar_one_or_none()
    if run is None or not run.screenshot_path:
        raise HTTPException(status_code=404, detail="screenshot_not_found")
    root = Path(settings.rpa_artifact_root).resolve()
    path = Path(run.screenshot_path)
    if path.is_absolute():
        candidate = path.resolve()
    else:
        candidate = (root / path.name).resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=403, detail="invalid_screenshot_path")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="screenshot_not_found")
    return FileResponse(candidate, media_type="image/png")
