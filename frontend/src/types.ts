export type Severity = "P1" | "P2" | "P3" | "P4";
export type IncidentStatus =
  | "RECEIVED"
  | "ANALYZING"
  | "AWAITING_APPROVAL"
  | "WORK_ORDER_CREATED"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "CLOSED"
  | "DUPLICATE"
  | "REJECTED"
  | "WORKFLOW_FAILED";
export type WorkOrderStatus = "OPEN" | "ASSIGNED" | "IN_PROGRESS" | "WAITING_PARTS" | "RESOLVED" | "CLOSED";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "TIMED_OUT";
export type CreationMethod = "API" | "RPA" | "MANUAL";
export type RpaStatus = "SUCCEEDED" | "FAILED" | "RUNNING";

export interface Equipment {
  id: number;
  code: string;
  name: string;
  line_code: string;
  location: string;
  criticality: string;
}

export interface Incident {
  id: number;
  incident_no: string;
  equipment_id: number;
  production_batch_id: number | null;
  incident_type: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  sla_due_at: string;
}

export interface IncidentCreateResponse {
  incident: Incident;
  duplicate: boolean;
  original_incident_id: number | null;
}

export interface WorkOrder {
  id: number;
  work_order_no: string;
  incident_id: number | null;
  title: string;
  description: string;
  status: WorkOrderStatus;
  priority: Severity;
  assigned_team: string | null;
  assignee: string | null;
  creation_method: CreationMethod;
  external_id: string | null;
  sla_due_at: string;
  resolved_at: string | null;
}

export interface Approval {
  id: number;
  incident_id: number;
  status: ApprovalStatus;
  approver: string | null;
  comment: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface WorkflowEvent {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
  work_order_id: number | null;
}

export interface RpaRun {
  id: number;
  work_order_id: number | null;
  status: RpaStatus;
  external_id: string | null;
  screenshot_path: string | null;
  steps: Array<Record<string, unknown>>;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
}

export interface AgentCause {
  cause: string;
  evidence: string;
}

export interface AgentOutput {
  summary: string;
  probable_causes: AgentCause[];
  recommended_actions: string[];
  missing_information: string[];
  risk_level: Severity;
  confidence: number;
  requires_human_approval: boolean;
}

export interface AnalysisRun {
  incident_id: number;
  analysis_run_id: number;
  provider: string;
  model: string;
  prompt_version: string;
  fallback_used: boolean;
  final_severity: Severity;
  requires_human_approval: boolean;
  agent_output: AgentOutput;
  rule_reasons: string[];
}

export interface DashboardSummary {
  total_incidents: number;
  open_incidents: number;
  total_work_orders: number;
  pending_approvals: number;
}

export interface SeverityBucket {
  severity: Severity;
  count: number;
}

export interface SlaMetrics {
  overdue_work_orders: number;
  due_soon_work_orders: number;
  overdue_incidents: number;
}

export interface DemoScenario {
  code: string;
  name: string;
  equipment_code: string;
  incident_type: string;
  severity: Severity;
}

export interface DemoRpaFallbackResponse {
  incident: Incident;
  work_order: WorkOrder;
  rpa_run: RpaRun | null;
  rpa_result: {
    success: boolean;
    external_id: string | null;
    screenshot_path: string | null;
    steps: Array<Record<string, unknown>>;
    error_code: string | null;
    error_message: string | null;
  };
}
