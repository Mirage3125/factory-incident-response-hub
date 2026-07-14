import type {
  AnalysisRun,
  Approval,
  DashboardSummary,
  DemoRpaFallbackResponse,
  DemoScenario,
  Equipment,
  Incident,
  IncidentCreateResponse,
  RpaRun,
  SeverityBucket,
  SlaMetrics,
  WorkOrder,
  WorkOrderStatus
} from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8100").replace(/\/$/, "");
const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 10000);

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: options.signal ?? controller.signal,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers
      }
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    if (!response.ok) {
      throw new ApiError(response.status, data?.detail ?? data ?? response.statusText);
    }
    return data as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(408, "Request timed out");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export const api = {
  baseUrl: API_BASE_URL,
  health: () => request<{ status: string }>("/health"),
  ready: () => request<{ status: string }>("/ready"),
  equipment: () => request<Equipment[]>("/api/equipment"),
  incidents: () => request<Incident[]>("/api/incidents"),
  incident: (id: number) => request<Incident>(`/api/incidents/${id}`),
  incidentTimeline: (id: number) => request<import("../types").WorkflowEvent[]>(`/api/incidents/${id}/timeline`),
  analyzeIncident: (id: number, force = false) =>
    request<AnalysisRun>(`/api/incidents/${id}/analyze`, { method: "POST", body: JSON.stringify({ force }) }, 30000),
  incidentAnalyses: (id: number) => request<AnalysisRun[]>(`/api/incidents/${id}/analysis-runs`),
  createIncident: (payload: Record<string, unknown>) =>
    request<IncidentCreateResponse>("/api/incidents", { method: "POST", body: JSON.stringify(payload) }),
  workOrders: () => request<WorkOrder[]>("/api/work-orders"),
  workOrder: (id: number) => request<WorkOrder>(`/api/work-orders/${id}`),
  updateWorkOrderStatus: (id: number, status: WorkOrderStatus) =>
    request<WorkOrder>(`/api/work-orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  assignWorkOrder: (id: number, assignedTeam: string, assignee?: string) =>
    request<WorkOrder>(`/api/work-orders/${id}/assign`, {
      method: "POST",
      body: JSON.stringify({ assigned_team: assignedTeam, assignee: assignee || null })
    }),
  resolveWorkOrder: (id: number, resolution: string) =>
    request<WorkOrder>(`/api/work-orders/${id}/resolve`, { method: "POST", body: JSON.stringify({ resolution }) }),
  pendingApprovals: () => request<Approval[]>("/api/approvals/pending"),
  approve: (id: number, approver: string, comment: string) =>
    request<Approval>(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ approver, comment }) }, 20000),
  reject: (id: number, approver: string, comment: string) =>
    request<Approval>(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ approver, comment }) }, 20000),
  dashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),
  severityDistribution: () => request<SeverityBucket[]>("/api/dashboard/severity-distribution"),
  recentIncidents: () => request<Incident[]>("/api/dashboard/recent-incidents"),
  slaMetrics: () => request<SlaMetrics>("/api/dashboard/sla-metrics"),
  demoScenarios: () => request<DemoScenario[]>("/api/demo/scenarios"),
  triggerScenario: (code: string) => request<IncidentCreateResponse>(`/api/demo/scenarios/${code}/trigger`, { method: "POST" }, 30000),
  triggerRpaFallback: () => request<DemoRpaFallbackResponse>("/api/demo/rpa-fallback", { method: "POST" }, 90000),
  rpaRuns: (workOrderId?: number) => request<RpaRun[]>(workOrderId ? `/api/rpa-runs?work_order_id=${workOrderId}` : "/api/rpa-runs"),
  rpaRunScreenshotUrl: (id: number) => `${API_BASE_URL}/api/rpa-runs/${id}/screenshot`
};
