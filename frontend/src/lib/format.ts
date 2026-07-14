import type { ApprovalStatus, CreationMethod, IncidentStatus, RpaStatus, Severity, WorkOrderStatus } from "../types";

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).formatToParts(date);
  const valueByType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${valueByType.year}-${valueByType.month}-${valueByType.day} ${valueByType.hour}:${valueByType.minute}`;
}

export function formatDurationMinutes(minutes: number | null | undefined): string {
  if (minutes == null || Number.isNaN(minutes)) return "-";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  return `${Math.floor(minutes / 60)}h ${Math.round(minutes % 60)}m`;
}

export function severityClass(severity: Severity): string {
  const classes: Record<Severity, string> = {
    P1: "bg-red-100 text-red-800 border-red-300",
    P2: "bg-amber-100 text-amber-800 border-amber-300",
    P3: "bg-sky-100 text-sky-800 border-sky-300",
    P4: "bg-slate-100 text-slate-700 border-slate-300"
  };
  return classes[severity];
}

const severityLabels: Record<Severity, string> = {
  P1: "P1 严重",
  P2: "P2 高",
  P3: "P3 中",
  P4: "P4 低"
};

const incidentStatusLabels: Record<IncidentStatus, string> = {
  RECEIVED: "已接收",
  ANALYZING: "正在分析",
  AWAITING_APPROVAL: "等待审批",
  WORK_ORDER_CREATED: "已创建工单",
  IN_PROGRESS: "处理中",
  RESOLVED: "已解决",
  CLOSED: "已关闭",
  DUPLICATE: "重复报警",
  REJECTED: "已驳回",
  WORKFLOW_FAILED: "自动流程执行失败"
};

const workOrderStatusLabels: Record<WorkOrderStatus, string> = {
  OPEN: "待分派",
  ASSIGNED: "已分派",
  IN_PROGRESS: "处理中",
  WAITING_PARTS: "等待备件",
  RESOLVED: "已解决",
  CLOSED: "已关闭"
};

const approvalStatusLabels: Record<ApprovalStatus, string> = {
  PENDING: "等待审批",
  APPROVED: "已批准",
  REJECTED: "已驳回",
  TIMED_OUT: "审批超时"
};

const creationMethodLabels: Record<CreationMethod, string> = {
  API: "MES API 创建",
  RPA: "RPA 自动录入",
  MANUAL: "人工创建"
};

const rpaStatusLabels: Record<RpaStatus, string> = {
  SUCCEEDED: "执行成功",
  FAILED: "执行失败",
  RUNNING: "执行中"
};

const incidentTypeLabels: Record<string, string> = {
  vibration: "设备振动异常",
  spindle_vibration: "主轴振动异常",
  defect_rate: "产品缺陷率升高",
  duplicate_demo_alarm: "重复报警",
  mes_api_failure: "MES 接口故障"
};

const workflowEventLabels: Record<string, string> = {
  INCIDENT_CREATED: "异常已创建",
  INCIDENT_DUPLICATED: "重复报警已合并",
  INCIDENT_ANALYZED: "系统分析完成",
  APPROVAL_REGISTERED: "审批任务已创建",
  APPROVAL_APPROVED: "审批已批准",
  APPROVAL_REJECTED: "审批已驳回",
  WORK_ORDER_CREATED: "工单已创建",
  WORK_ORDER_STATUS_CHANGED: "工单状态已更新",
  RPA_RUN_CREATED: "RPA 自动录入已记录",
  WORKFLOW_FAILED: "自动流程执行失败",
  SLA_ESCALATED: "SLA 超时升级"
};

export function displaySeverity(value: Severity): string {
  return severityLabels[value];
}

export function displayIncidentStatus(value: IncidentStatus): string {
  return incidentStatusLabels[value] ?? value;
}

export function displayWorkOrderStatus(value: WorkOrderStatus): string {
  return workOrderStatusLabels[value] ?? value;
}

export function displayApprovalStatus(value: ApprovalStatus): string {
  return approvalStatusLabels[value] ?? value;
}

export function displayCreationMethod(value: CreationMethod): string {
  return creationMethodLabels[value] ?? value;
}

export function displayRpaStatus(value: RpaStatus): string {
  return rpaStatusLabels[value] ?? value;
}

export function displayIncidentType(value: string): string {
  return incidentTypeLabels[value] ?? value.replace(/_/g, " ");
}

export function displayWorkflowEvent(value: string): string {
  return workflowEventLabels[value] ?? value.replace(/_/g, " ");
}

export function displayBoolean(value: boolean | null | undefined): string {
  if (value == null) return "-";
  return value ? "是" : "否";
}

export function displayBadgeValue(value: string, kind: "severity" | "status" = "status"): string {
  if (kind === "severity" && value in severityLabels) return displaySeverity(value as Severity);
  if (value in incidentStatusLabels) return displayIncidentStatus(value as IncidentStatus);
  if (value in workOrderStatusLabels) return displayWorkOrderStatus(value as WorkOrderStatus);
  if (value in approvalStatusLabels) return displayApprovalStatus(value as ApprovalStatus);
  if (value in creationMethodLabels) return displayCreationMethod(value as CreationMethod);
  if (value in rpaStatusLabels) return displayRpaStatus(value as RpaStatus);
  if (value === "APPROVAL_REQUIRED") return "需要人工审批";
  if (value === "NO_APPROVAL") return "无需人工审批";
  return value;
}

export function formatErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (error instanceof TypeError || /network|fetch|load failed/i.test(message)) return "网络连接失败，请检查服务状态";
  if (/request failed/i.test(message)) return "请求失败";
  return message || "请求失败";
}

export function statusClass(status: string): string {
  if (status.includes("FAILED") || status.includes("REJECTED")) return "bg-red-50 text-red-800 border-red-200";
  if (status.includes("PENDING") || status.includes("AWAITING") || status.includes("WAITING")) return "bg-amber-50 text-amber-800 border-amber-200";
  if (status.includes("RESOLVED") || status.includes("CLOSED") || status.includes("SUCCEEDED")) return "bg-emerald-50 text-emerald-800 border-emerald-200";
  return "bg-slate-50 text-slate-700 border-slate-200";
}

export function nextWorkOrderAction(status: WorkOrderStatus): WorkOrderStatus | null {
  const next: Record<WorkOrderStatus, WorkOrderStatus | null> = {
    OPEN: "ASSIGNED",
    ASSIGNED: "IN_PROGRESS",
    IN_PROGRESS: "RESOLVED",
    WAITING_PARTS: "IN_PROGRESS",
    RESOLVED: "CLOSED",
    CLOSED: null
  };
  return next[status];
}
