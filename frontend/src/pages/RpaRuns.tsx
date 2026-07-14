import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";

export function RpaRuns() {
  const runs = useQuery({ queryKey: ["rpa-runs"], queryFn: () => api.rpaRuns() });

  if (runs.isLoading) return <LoadingState label="RPA 执行记录加载中" />;
  if (runs.error) return <ErrorState error={runs.error} />;

  return (
    <Section title="RPA 执行记录">
      <p className="mb-4 text-sm text-slate-600">当 MES 接口不可用时，系统会通过 RPA 模拟人工操作完成工单录入，并保存执行结果、外部工单号和截图。</p>
      {(runs.data ?? []).length === 0 ? <EmptyState label="暂无 RPA 执行记录。" /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {(runs.data ?? []).map((run) => (
            <div key={run.id} className="border border-slate-200 p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-semibold">执行记录 #{run.id}</span>
                <Badge value={run.status} />
                <span className="text-xs text-slate-500">{formatDateTime(run.created_at)}</span>
              </div>
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div><dt className="text-slate-500">关联工单</dt><dd>{run.work_order_id ?? "-"}</dd></div>
                <div><dt className="text-slate-500">MES 外部工单</dt><dd>{run.external_id ?? "暂未返回"}</dd></div>
                <div><dt className="text-slate-500">错误代码</dt><dd>{run.error_code ?? "无"}</dd></div>
                <div><dt className="text-slate-500">执行截图</dt><dd>{run.screenshot_path ? "已保存" : "无"}</dd></div>
              </dl>
              <div className="mt-3 border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
                {run.steps.length === 0 ? "暂无步骤日志。" : run.steps.map((step, index) => <div className="break-words" key={index}>步骤 {index + 1}：{JSON.stringify(step)}</div>)}
              </div>
              {run.screenshot_path ? <img className="mt-3 max-h-64 w-full border border-slate-200 object-contain" src={api.rpaRunScreenshotUrl(run.id)} alt={`RPA 执行记录 ${run.id} 截图`} /> : null}
              {run.error_message ? <p className="mt-2 text-sm text-red-700">{run.error_message}</p> : null}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}
