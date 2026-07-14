import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";

export function ApprovalCenter() {
  const queryClient = useQueryClient();
  const approvals = useQuery({ queryKey: ["approvals-pending"], queryFn: api.pendingApprovals });
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: api.incidents });
  const [comments, setComments] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approve" | "reject" }) => {
      setBusyId(id);
      const comment = comments[id] ?? "";
      return decision === "approve" ? api.approve(id, "frontend-operator", comment) : api.reject(id, "frontend-operator", comment);
    },
    onSettled: async () => {
      setBusyId(null);
      await queryClient.invalidateQueries({ queryKey: ["approvals-pending"] });
      await queryClient.invalidateQueries({ queryKey: ["incidents"] });
    }
  });

  if (approvals.isLoading || incidents.isLoading) return <LoadingState label="审批任务加载中" />;
  const error = approvals.error ?? incidents.error ?? decide.error;
  if (error) return <ErrorState error={error} />;

  return (
    <Section title="审批中心">
      {(approvals.data ?? []).length === 0 ? <EmptyState label="暂无待审批任务。" /> : (
        <div className="space-y-3">
          {(approvals.data ?? []).map((approval) => {
            const incident = incidents.data?.find((item) => item.id === approval.incident_id);
            const disabled = decide.isPending && busyId === approval.id;
            return (
              <div key={approval.id} className="border border-slate-200 p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{incident?.incident_no ?? `异常 ${approval.incident_id}`}</span>
                  {incident ? <Badge value={incident.severity} kind="severity" /> : null}
                  <Badge value={approval.status} />
                  <span className="text-xs text-slate-500">{formatDateTime(approval.created_at)}</span>
                </div>
                <p className="mb-1 text-sm text-slate-700">{incident?.title ?? "正在从后端记录加载审批上下文。"}</p>
                <p className="mb-3 text-xs text-slate-500">P1 严重异常需要人工确认后继续工单流转。</p>
                <textarea
                  className="mb-3 min-h-20 w-full border border-slate-300 px-3 py-2 text-sm"
                  placeholder="填写审批意见"
                  value={comments[approval.id] ?? ""}
                  onChange={(event) => setComments((value) => ({ ...value, [approval.id]: event.target.value }))}
                />
                <div className="flex flex-wrap gap-2">
                  <button className="inline-flex items-center gap-2 border border-emerald-700 bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={disabled} onClick={() => decide.mutate({ id: approval.id, decision: "approve" })}>
                    <Check className="h-4 w-4" aria-hidden="true" /> 批准
                  </button>
                  <button className="inline-flex items-center gap-2 border border-red-700 bg-red-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={disabled} onClick={() => decide.mutate({ id: approval.id, decision: "reject" })}>
                    <X className="h-4 w-4" aria-hidden="true" /> 驳回
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Section>
  );
}
