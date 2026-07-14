import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertCircle, Clock, ClipboardList, ShieldCheck, Wrench } from "lucide-react";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";

export function Dashboard() {
  const summary = useQuery({ queryKey: ["dashboard-summary"], queryFn: api.dashboardSummary });
  const severity = useQuery({ queryKey: ["severity-distribution"], queryFn: api.severityDistribution });
  const recent = useQuery({ queryKey: ["recent-incidents"], queryFn: api.recentIncidents });
  const sla = useQuery({ queryKey: ["sla-metrics"], queryFn: api.slaMetrics });
  const workOrders = useQuery({ queryKey: ["work-orders"], queryFn: api.workOrders });
  const approvals = useQuery({ queryKey: ["approvals-pending"], queryFn: api.pendingApprovals });

  if (summary.isLoading || severity.isLoading || recent.isLoading || sla.isLoading) return <LoadingState label="运行总览加载中" />;
  const error = summary.error ?? severity.error ?? recent.error ?? sla.error ?? workOrders.error ?? approvals.error;
  if (error) return <ErrorState error={error} />;

  const incidents = recent.data ?? [];
  const today = new Date().toDateString();
  const todayCount = incidents.filter((item) => new Date(item.first_seen_at).toDateString() === today).length;
  const activeWorkOrders = (workOrders.data ?? []).filter((item) => !["RESOLVED", "CLOSED"].includes(item.status)).length;
  const p1p2 = (severity.data ?? []).filter((item) => item.severity === "P1" || item.severity === "P2").reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Metric icon={<AlertCircle />} label="今日异常" value={todayCount} tone="text-slate-900" />
        <Metric icon={<ShieldCheck />} label="高优先级异常" value={p1p2} tone="text-red-700" />
        <Metric icon={<ClipboardList />} label="待审批任务" value={approvals.data?.length ?? summary.data?.pending_approvals ?? 0} tone="text-amber-700" />
        <Metric icon={<Wrench />} label="处理中工单" value={activeWorkOrders} tone="text-teal-800" />
        <Metric icon={<Clock />} label="已超时任务" value={(sla.data?.overdue_incidents ?? 0) + (sla.data?.overdue_work_orders ?? 0)} tone="text-red-700" />
        <Metric icon={<Clock />} label="即将到期" value={sla.data?.due_soon_work_orders ?? 0} tone="text-amber-700" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Section title="最近异常">
          {incidents.length === 0 ? (
            <EmptyState label="暂无最近异常。" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] border-collapse">
                <thead className="table-head">
                  <tr>
                    <th className="w-36 px-3 py-2">异常编号</th>
                    <th className="px-3 py-2">异常内容</th>
                    <th className="w-28 px-3 py-2">严重等级</th>
                    <th className="w-32 px-3 py-2">处理状态</th>
                    <th className="w-40 px-3 py-2">最近发生时间</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((item) => (
                    <tr key={item.id}>
                      <td className="table-cell font-medium">
                        <Link className="text-teal-800 hover:underline" to={`/incidents/${item.id}`}>
                          {item.incident_no}
                        </Link>
                      </td>
                      <td className="table-cell">{item.title}</td>
                      <td className="table-cell">
                        <Badge value={item.severity} kind="severity" />
                      </td>
                      <td className="table-cell">
                        <Badge value={item.status} />
                      </td>
                      <td className="table-cell">{formatDateTime(item.last_seen_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="异常等级分布">
          <div className="space-y-3">
            {(severity.data ?? []).map((bucket) => (
              <div key={bucket.severity}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <Badge value={bucket.severity} kind="severity" />
                  <span className="font-semibold">{bucket.count}</span>
                </div>
                <div className="h-2 bg-slate-200">
                  <div className="h-2 bg-teal-700" style={{ width: `${Math.min(bucket.count * 10, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function Metric({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number; tone: string }) {
  return (
    <div className="metric">
      <div className="mb-2 flex items-center justify-between text-slate-500">
        <span className="text-xs font-semibold tracking-normal">{label}</span>
        <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
      </div>
      <div className={`text-3xl font-semibold ${tone}`}>{value}</div>
    </div>
  );
}
