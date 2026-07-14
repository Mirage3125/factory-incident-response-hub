import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Play } from "lucide-react";
import { api } from "../lib/api";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";
import type { IncidentCreateResponse } from "../types";

interface DemoResult {
  label: string;
  incidentId: number;
  incidentNo: string;
  duplicate?: boolean;
  extra?: string;
  rpaRunId?: number;
}

const scenarioCopy = {
  p1: {
    name: "主轴振动严重异常",
    description: "模拟设备振动超过安全阈值，系统会判断为严重异常并进入审批流程。"
  },
  p2: {
    name: "产品缺陷率升高",
    description: "模拟视觉检测发现缺陷率明显升高，系统会分析原因并创建质量工单。"
  },
  duplicate: {
    name: "重复报警",
    description: "验证相同报警不会重复创建多张工单。"
  },
  rpa: {
    name: "MES 接口故障",
    description: "模拟外部系统接口不可用，验证系统自动切换到 RPA 完成工单录入。"
  }
};

export function DemoScenarios() {
  const queryClient = useQueryClient();
  const scenarios = useQuery({ queryKey: ["demo-scenarios"], queryFn: api.demoScenarios });
  const [result, setResult] = useState<DemoResult | null>(null);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["incidents"] }),
      queryClient.invalidateQueries({ queryKey: ["work-orders"] }),
      queryClient.invalidateQueries({ queryKey: ["rpa-runs"] }),
      queryClient.invalidateQueries({ queryKey: ["recent-incidents"] })
    ]);
  };

  const runScenario = useMutation({
    mutationFn: async (code: string) => {
      const response = await api.triggerScenario(code);
      await api.analyzeIncident(response.incident.id, true);
      return response;
    },
    onSuccess: async (response, code) => {
      setResult({
        label: code,
        incidentId: response.incident.id,
        incidentNo: response.incident.incident_no,
        duplicate: response.duplicate
      });
      await invalidate();
    }
  });

  const runDuplicate = useMutation({
    mutationFn: async () => {
      const payload = {
        equipment_code: "VISION-01",
        incident_type: "duplicate_demo_alarm",
        title: "重复报警演示",
        description: "同一设备、同一类型和同一批次在去重窗口内重复上报。",
        severity: "P2",
        production_batch_no: "BATCH-20260714-001"
      };
      await api.createIncident(payload);
      return api.createIncident(payload) as Promise<IncidentCreateResponse>;
    },
    onSuccess: async (response) => {
      setResult({
        label: "duplicate-alert",
        incidentId: response.incident.id,
        incidentNo: response.incident.incident_no,
        duplicate: response.duplicate,
        extra: `发生次数：${response.incident.occurrence_count}`
      });
      await invalidate();
    }
  });

  const runRpa = useMutation({
    mutationFn: api.triggerRpaFallback,
    onSuccess: async (response) => {
      setResult({
        label: "mes-api-failure-rpa-fallback",
        incidentId: response.incident.id,
        incidentNo: response.incident.incident_no,
        rpaRunId: response.rpa_run?.id,
        extra: `工单 ${response.work_order.work_order_no}，MES 外部工单：${response.work_order.external_id ?? "暂未返回"}`
      });
      await invalidate();
    }
  });

  const error = scenarios.error ?? runScenario.error ?? runDuplicate.error ?? runRpa.error;
  if (scenarios.isLoading) return <LoadingState label="场景演示加载中" />;
  if (error) return <ErrorState error={error} />;

  const p1 = scenarios.data?.find((item) => item.code === "cnc-vibration-p1");
  const p2 = scenarios.data?.find((item) => item.code === "vision-defect-p2");
  const busy = runScenario.isPending || runDuplicate.isPending || runRpa.isPending;

  return (
    <div className="space-y-4">
      <Section title="场景演示">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <DemoButton label={scenarioCopy.p1.name} description={scenarioCopy.p1.description} badge={p1?.severity ?? "P1"} disabled={busy} onClick={() => runScenario.mutate("cnc-vibration-p1")} />
          <DemoButton label={scenarioCopy.p2.name} description={scenarioCopy.p2.description} badge={p2?.severity ?? "P2"} disabled={busy} onClick={() => runScenario.mutate("vision-defect-p2")} />
          <DemoButton label={scenarioCopy.duplicate.name} description={scenarioCopy.duplicate.description} badge="P2" disabled={busy} onClick={() => runDuplicate.mutate()} />
          <DemoButton label={scenarioCopy.rpa.name} description={scenarioCopy.rpa.description} badge="RPA" disabled={busy} onClick={() => runRpa.mutate()} />
        </div>
      </Section>
      <Section title="查看处理过程">
        {!result ? <EmptyState label="当前浏览器会话中尚未触发场景。" /> : (
          <div className="text-sm">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="font-semibold">{displayScenarioLabel(result.label)}</span>
              {result.duplicate ? <Badge value="重复报警" /> : null}
            </div>
            <p>
              查看异常详情{" "}
              <Link className="font-semibold text-teal-800 hover:underline" to={`/incidents/${result.incidentId}`}>
                {result.incidentNo}
              </Link>
            </p>
            {result.extra ? <p className="mt-1 text-slate-700">{result.extra}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Link className="border border-teal-700 px-3 py-1 text-xs font-semibold text-teal-800" to={`/incidents/${result.incidentId}`}>查看异常详情</Link>
              <Link className="border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700" to="/work-orders">查看工单</Link>
              {result.rpaRunId ? <Link className="border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700" to="/rpa-runs">查看 RPA 记录</Link> : null}
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}

function DemoButton({ label, description, badge, disabled, onClick }: { label: string; description: string; badge: string; disabled: boolean; onClick: () => void }) {
  return (
    <button className="flex min-h-44 flex-col justify-between border border-slate-300 bg-slate-50 p-4 text-left hover:border-teal-700 disabled:opacity-50" disabled={disabled} onClick={onClick}>
      <span className="flex items-center justify-between gap-3">
        <span className="font-semibold text-slate-900">{label}</span>
        <Play className="h-4 w-4 text-teal-700" aria-hidden="true" />
      </span>
      <span className="mt-3 text-sm leading-6 text-slate-600">{description}</span>
      <Badge value={badge} kind={badge.startsWith("P") ? "severity" : "status"} />
      <span className="mt-3 text-xs font-semibold text-teal-800">触发场景</span>
    </button>
  );
}

function displayScenarioLabel(label: string): string {
  const labels: Record<string, string> = {
    "cnc-vibration-p1": scenarioCopy.p1.name,
    "vision-defect-p2": scenarioCopy.p2.name,
    "duplicate-alert": scenarioCopy.duplicate.name,
    "mes-api-failure-rpa-fallback": scenarioCopy.rpa.name
  };
  return labels[label] ?? label;
}
