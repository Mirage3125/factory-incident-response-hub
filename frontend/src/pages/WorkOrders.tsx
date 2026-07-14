import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { displayWorkOrderStatus, formatDateTime, nextWorkOrderAction } from "../lib/format";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";

export function WorkOrders() {
  const queryClient = useQueryClient();
  const workOrders = useQuery({ queryKey: ["work-orders"], queryFn: api.workOrders });
  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: ReturnType<typeof nextWorkOrderAction> }) => {
      if (!status) throw new Error("没有可更新的下一状态");
      return api.updateWorkOrderStatus(id, status);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["work-orders"] });
    }
  });

  if (workOrders.isLoading) return <LoadingState label="工单加载中" />;
  const error = workOrders.error ?? updateStatus.error;
  if (error) return <ErrorState error={error} />;

  return (
    <Section title="工单管理">
      {(workOrders.data ?? []).length === 0 ? <EmptyState label="暂无工单。" /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="w-40 px-3 py-2">工单编号</th>
                <th className="px-3 py-2">工单内容</th>
                <th className="w-28 px-3 py-2">优先级</th>
                <th className="w-28 px-3 py-2">工单状态</th>
                <th className="w-32 px-3 py-2">负责人</th>
                <th className="w-40 px-3 py-2">SLA 处理时限</th>
                <th className="w-32 px-3 py-2">创建方式</th>
                <th className="w-44 px-3 py-2">MES 外部工单</th>
                <th className="w-32 px-3 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {(workOrders.data ?? []).map((order) => {
                const next = nextWorkOrderAction(order.status);
                return (
                  <tr key={order.id}>
                    <td className="table-cell font-medium">{order.work_order_no}</td>
                    <td className="table-cell">{order.title}</td>
                    <td className="table-cell"><Badge value={order.priority} kind="severity" /></td>
                    <td className="table-cell"><Badge value={order.status} /></td>
                    <td className="table-cell">{order.assignee ?? order.assigned_team ?? "-"}</td>
                    <td className="table-cell">{formatDateTime(order.sla_due_at)}</td>
                    <td className="table-cell"><Badge value={order.creation_method} /></td>
                    <td className="table-cell">{order.external_id ?? "暂未创建"}</td>
                    <td className="table-cell">
                      <button
                        className="border border-teal-700 px-3 py-1 text-xs font-semibold text-teal-800 disabled:opacity-40"
                        disabled={!next || updateStatus.isPending}
                        onClick={() => updateStatus.mutate({ id: order.id, status: next })}
                      >
                        {next ? `更新为${displayWorkOrderStatus(next)}` : "无需操作"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
