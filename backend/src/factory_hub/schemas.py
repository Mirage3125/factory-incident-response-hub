from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from factory_hub.domain.enums import ApprovalStatus, IncidentStatus, RpaStatus, Severity, WorkOrderCreationMethod, WorkOrderStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EquipmentRead(ApiModel):
    id: int
    code: str
    name: str
    line_code: str
    location: str
    criticality: str


class MaintenanceRecordRead(ApiModel):
    id: int
    equipment_id: int
    performed_at: datetime
    summary: str
    technician: str


class IncidentCreate(BaseModel):
    equipment_code: str
    incident_type: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    severity: Severity
    production_batch_no: str | None = None
    occurred_at: datetime | None = None


class IncidentRead(ApiModel):
    id: int
    incident_no: str
    equipment_id: int
    production_batch_id: int | None
    incident_type: str
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    sla_due_at: datetime


class IncidentCreateResponse(BaseModel):
    incident: IncidentRead
    duplicate: bool
    original_incident_id: int | None = None


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class WorkOrderCreate(BaseModel):
    incident_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    priority: Severity
    assigned_team: str | None = None
    assignee: str | None = None
    creation_method: WorkOrderCreationMethod = WorkOrderCreationMethod.API


class WorkOrderRead(ApiModel):
    id: int
    work_order_no: str
    incident_id: int | None
    title: str
    description: str
    status: WorkOrderStatus
    priority: Severity
    assigned_team: str | None
    assignee: str | None
    creation_method: WorkOrderCreationMethod
    external_id: str | None
    sla_due_at: datetime
    resolved_at: datetime | None


class WorkOrderAssign(BaseModel):
    assigned_team: str
    assignee: str | None = None


class WorkOrderStatusUpdate(BaseModel):
    status: WorkOrderStatus


class WorkOrderResolve(BaseModel):
    resolution: str = Field(min_length=1, max_length=4000)


class ApprovalRead(ApiModel):
    id: int
    incident_id: int
    status: ApprovalStatus
    approver: str | None
    comment: str | None
    decided_at: datetime | None
    created_at: datetime


class ApprovalDecision(BaseModel):
    approver: str = Field(min_length=1, max_length=120)
    comment: str | None = None


class WorkflowEventCreate(BaseModel):
    incident_id: int | None = None
    work_order_id: int | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationCreate(BaseModel):
    target: str
    message: str
    status: str = "QUEUED"
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalRegister(BaseModel):
    incident_id: int
    resume_url: str


class RpaRunCreate(BaseModel):
    work_order_id: int | None = None
    status: RpaStatus
    external_id: str | None = None
    screenshot_path: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class RpaRunRead(ApiModel):
    id: int
    work_order_id: int | None
    status: RpaStatus
    external_id: str | None
    screenshot_path: str | None
    steps: list[dict[str, Any]]
    error_code: str | None
    error_message: str | None
    created_at: datetime


class ErrorRecordCreate(BaseModel):
    incident_id: int | None = None
    work_order_id: int | None = None
    error_code: str
    error_message: str


class CloseCaseRequest(BaseModel):
    incident_id: int
    resolution: str = Field(min_length=1, max_length=4000)


class KnowledgeCaseRead(ApiModel):
    id: int
    incident_id: int | None
    title: str
    summary: str
    resolution: str


class SlaEscalationScanRequest(BaseModel):
    level: int = Field(default=1, ge=1, le=3)


class SlaEscalationScanResponse(BaseModel):
    scanned_work_orders: int
    created_notifications: int


class RpaWorkOrderRequest(BaseModel):
    work_order_id: int
    reason: str = Field(min_length=1, max_length=500)


class RpaWorkOrderResponse(BaseModel):
    success: bool
    external_id: str | None = None
    screenshot_path: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class ExternalWorkOrderResult(BaseModel):
    work_order_id: int
    external_id: str = Field(min_length=1, max_length=120)
    creation_method: WorkOrderCreationMethod = WorkOrderCreationMethod.API


class IdResponse(BaseModel):
    id: int


class DemoScenarioRead(BaseModel):
    code: str
    name: str
    equipment_code: str
    incident_type: str
    severity: Severity


class DemoRpaFallbackResponse(BaseModel):
    incident: IncidentRead
    work_order: WorkOrderRead
    rpa_run: RpaRunRead | None
    rpa_result: RpaWorkOrderResponse


class DashboardSummary(BaseModel):
    total_incidents: int
    open_incidents: int
    total_work_orders: int
    pending_approvals: int


class SeverityBucket(BaseModel):
    severity: Severity
    count: int


class SlaMetrics(BaseModel):
    overdue_work_orders: int
    due_soon_work_orders: int
    overdue_incidents: int
