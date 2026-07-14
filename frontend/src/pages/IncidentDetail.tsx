import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Bot, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { displayBoolean, displayIncidentType, displayWorkflowEvent, formatDateTime } from "../lib/format";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";

export function IncidentDetail() {
  const id = Number(useParams().id);
  const queryClient = useQueryClient();
  const incident = useQuery({ queryKey: ["incident", id], queryFn: () => api.incident(id), enabled: Number.isFinite(id) });
  const timeline = useQuery({ queryKey: ["incident-timeline", id], queryFn: () => api.incidentTimeline(id), enabled: Number.isFinite(id) });
  const analyses = useQuery({ queryKey: ["incident-analyses", id], queryFn: () => api.incidentAnalyses(id), enabled: Number.isFinite(id) });
  const workOrders = useQuery({ queryKey: ["work-orders"], queryFn: api.workOrders });
  const approvals = useQuery({ queryKey: ["approvals-pending"], queryFn: api.pendingApprovals });
  const rpaRuns = useQuery({ queryKey: ["rpa-runs"], queryFn: () => api.rpaRuns() });

  const analyze = useMutation({
    mutationFn: () => api.analyzeIncident(id, true),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["incident", id] }),
        queryClient.invalidateQueries({ queryKey: ["incident-analyses", id] }),
        queryClient.invalidateQueries({ queryKey: ["approvals-pending"] })
      ]);
    }
  });

  const linkedWorkOrders = useMemo(() => (workOrders.data ?? []).filter((item) => item.incident_id === id), [id, workOrders.data]);
  const linkedRpaRuns = useMemo(() => (rpaRuns.data ?? []).filter((run) => linkedWorkOrders.some((order) => order.id === run.work_order_id)), [linkedWorkOrders, rpaRuns.data]);
  const latestAnalysis = analyses.data?.[0];

  if (incident.isLoading || timeline.isLoading || analyses.isLoading || workOrders.isLoading || approvals.isLoading || rpaRuns.isLoading) {
    return <LoadingState label="异常详情加载中" />;
  }
  const error = incident.error ?? timeline.error ?? analyses.error ?? workOrders.error ?? approvals.error ?? rpaRuns.error ?? analyze.error;
  if (error) return <ErrorState error={error} />;
  if (!incident.data) return <EmptyState label="未找到该异常。" />;
  const pendingApproval = approvals.data?.find((item) => item.incident_id === id);
  const needsApproval = latestAnalysis?.requires_human_approval ?? incident.data.status === "AWAITING_APPROVAL";

  return (
    <div className="space-y-4">
      <Section
        title={`${incident.data.incident_no} 异常详情`}
        action={
          <button
            className="inline-flex items-center gap-2 border border-teal-700 bg-teal-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            disabled={analyze.isPending}
            onClick={() => analyze.mutate()}
          >
            <RefreshCw className={`h-4 w-4 ${analyze.isPending ? "animate-spin" : ""}`} aria-hidden="true" />
            重新分析
          </button>
        }
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div>
            <h3 className="text-lg font-semibold">{incident.data.title}</h3>
            <p className="mt-2 text-sm text-slate-700">{incident.data.description}</p>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2">
              <Info label="发生了什么" value={displayIncidentType(incident.data.incident_type)} />
              <Info label="涉及设备" value={`设备 ID ${incident.data.equipment_id}`} />
              <Info label="发生次数" value={`${incident.data.occurrence_count} 次`} />
              <Info label="首次发生时间" value={formatDateTime(incident.data.first_seen_at)} />
              <Info label="SLA 处理时限" value={formatDateTime(incident.data.sla_due_at)} />
              <Info label="是否需要审批" value={displayBoolean(needsApproval)} />
            </dl>
          </div>
          <div className="space-y-2">
            <p className="text-xs font-semibold text-slate-500">当前严重程度</p>
            <Badge value={incident.data.severity} kind="severity" />
            <p className="pt-2 text-xs font-semibold text-slate-500">处理状态</p>
            <Badge value={incident.data.status} />
          </div>
        </div>
      </Section>

      <Section title="系统分析建议">
        {!latestAnalysis ? (
          <EmptyState label="暂无系统分析结果，可点击重新分析生成辅助建议。" />
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">由 Agent 自动生成，仅作为辅助建议，最终等级由规则引擎确认。</p>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Bot className="h-4 w-4 text-teal-700" aria-hidden="true" />
              <span>Agent 分析建议</span>
              <span className="text-slate-500">{latestAnalysis.provider} / {latestAnalysis.model}</span>
              <span className="text-slate-600">最终异常等级</span>
              <Badge value={latestAnalysis.final_severity} kind="severity" />
              <Badge value={latestAnalysis.requires_human_approval ? "APPROVAL_REQUIRED" : "NO_APPROVAL"} />
              <span>置信度 {(latestAnalysis.agent_output.confidence * 100).toFixed(0)}%</span>
            </div>
            <Info label="系统分析结果" value={latestAnalysis.agent_output.summary} />
            <p className="text-sm text-slate-700">{latestAnalysis.agent_output.summary}</p>
            <div className="grid gap-4 md:grid-cols-3">
              <List title="可能原因" items={latestAnalysis.agent_output.probable_causes.map((item) => `${item.cause}：${item.evidence}`)} />
              <List title="建议处理措施" items={latestAnalysis.agent_output.recommended_actions} />
              <List title="规则引擎结果" items={latestAnalysis.rule_reasons} />
            </div>
          </div>
        )}
      </Section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Section title="当前工单状态">
          {linkedWorkOrders.length === 0 ? <EmptyState label="暂无关联工单。" /> : linkedWorkOrders.map((order) => (
            <div key={order.id} className="border-b border-slate-200 py-3 last:border-0">
              <Link className="font-semibold text-teal-800 hover:underline" to="/work-orders">{order.work_order_no}</Link>
              <div className="mt-1 flex flex-wrap gap-2"><Badge value={order.priority} kind="severity" /><Badge value={order.status} /><Badge value={order.creation_method} /></div>
              <p className="mt-1 text-sm text-slate-700">{order.title}</p>
              <p className="text-xs text-slate-500">MES 外部工单：{order.external_id ?? "暂未创建"}</p>
            </div>
          ))}
          <div className="mt-3 border-t border-slate-200 pt-3 text-sm text-slate-700">
            人工审批：{pendingApproval ? "等待审批中心处理" : needsApproval ? "需要审批，暂无待办记录" : "无需审批或已处理"}
          </div>
        </Section>
        <Section title="处理过程">
          {(timeline.data ?? []).length === 0 ? <EmptyState label="暂无流程记录。" /> : (
            <ol className="space-y-3">
              {(timeline.data ?? []).map((event) => (
                <li key={event.id} className="border-l-2 border-teal-700 pl-3">
                  <div className="text-sm font-semibold">{displayWorkflowEvent(event.event_type)}</div>
                  <div className="text-xs text-slate-500">{formatDateTime(event.created_at)}</div>
                </li>
              ))}
            </ol>
          )}
        </Section>
      </div>

      <Section title="备用自动化处理记录">
        <p className="mb-3 text-sm text-slate-600">当 MES 接口不可用时，系统会通过 RPA 模拟人工操作完成工单录入。</p>
        {linkedRpaRuns.length === 0 ? <EmptyState label="暂无关联的 RPA 自动录入记录。" /> : (
          <div className="grid gap-3 md:grid-cols-2">
            {linkedRpaRuns.map((run) => (
              <div key={run.id} className="border border-slate-200 p-3">
                <div className="mb-2 flex items-center justify-between"><Badge value={run.status} /><span className="text-xs text-slate-500">{formatDateTime(run.created_at)}</span></div>
                <p className="text-sm">MES 外部工单：{run.external_id ?? "暂未返回"}</p>
                {run.screenshot_path ? <img className="mt-3 max-h-56 w-full border border-slate-200 object-contain" src={api.rpaRunScreenshotUrl(run.id)} alt={`RPA 执行记录 ${run.id} 截图`} /> : null}
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return <div className="border border-slate-200 bg-slate-50 px-3 py-2"><dt className="text-xs text-slate-500">{label}</dt><dd className="break-words text-sm font-semibold">{value}</dd></div>;
}

function List({ title, items }: { title: string; items: string[] }) {
  return <div><h4 className="mb-2 text-sm font-semibold">{title}</h4>{items.length === 0 ? <p className="text-sm text-slate-500">暂无数据</p> : <ul className="space-y-1 text-sm text-slate-700">{items.map((item) => <li className="break-words" key={item}>{item}</li>)}</ul>}</div>;
}
