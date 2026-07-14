import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { displayIncidentStatus, displayIncidentType, displaySeverity, formatDateTime } from "../lib/format";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/State";
import { Section } from "../components/Section";
import type { IncidentStatus, Severity } from "../types";

const PAGE_SIZE = 10;
const incidentStatuses: IncidentStatus[] = ["RECEIVED", "ANALYZING", "AWAITING_APPROVAL", "WORK_ORDER_CREATED", "IN_PROGRESS", "RESOLVED", "CLOSED", "WORKFLOW_FAILED"];
const severities: Severity[] = ["P1", "P2", "P3", "P4"];

export function IncidentList() {
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: api.incidents });
  const equipment = useQuery({ queryKey: ["equipment"], queryFn: api.equipment });
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    return (incidents.data ?? []).filter((item) => {
      const text = `${item.incident_no} ${item.title} ${item.description} ${item.incident_type}`.toLowerCase();
      return (
        (!status || item.status === status) &&
        (!severity || item.severity === severity) &&
        (!equipmentId || item.equipment_id === Number(equipmentId)) &&
        (!keyword || text.includes(keyword.toLowerCase()))
      );
    });
  }, [equipmentId, incidents.data, keyword, severity, status]);

  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  if (incidents.isLoading || equipment.isLoading) return <LoadingState label="异常事件加载中" />;
  const error = incidents.error ?? equipment.error;
  if (error) return <ErrorState error={error} />;

  return (
    <Section title="异常事件">
      <div className="mb-4 grid gap-2 md:grid-cols-5">
        <select className="border border-slate-300 px-2 py-2 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">全部状态</option>
          {incidentStatuses.map((item) => (
            <option key={item} value={item}>{displayIncidentStatus(item)}</option>
          ))}
        </select>
        <select className="border border-slate-300 px-2 py-2 text-sm" value={severity} onChange={(event) => setSeverity(event.target.value)}>
          <option value="">全部等级</option>
          {severities.map((item) => (
            <option key={item} value={item}>{displaySeverity(item)}</option>
          ))}
        </select>
        <select className="border border-slate-300 px-2 py-2 text-sm" value={equipmentId} onChange={(event) => setEquipmentId(event.target.value)}>
          <option value="">全部设备</option>
          {(equipment.data ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.code}
            </option>
          ))}
        </select>
        <input className="border border-slate-300 px-2 py-2 text-sm md:col-span-2" placeholder="搜索异常编号、内容或类型" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
      </div>
      {pageItems.length === 0 ? (
        <EmptyState label="暂无符合条件的异常。" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse">
            <thead className="table-head">
              <tr>
                <th className="w-36 px-3 py-2">异常编号</th>
                <th className="px-3 py-2">异常内容</th>
                <th className="w-36 px-3 py-2">异常类型</th>
                <th className="w-28 px-3 py-2">严重等级</th>
                <th className="w-32 px-3 py-2">处理状态</th>
                <th className="w-24 px-3 py-2">发生次数</th>
                <th className="w-40 px-3 py-2">SLA 处理时限</th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((item) => (
                <tr key={item.id}>
                  <td className="table-cell font-medium">
                    <Link className="text-teal-800 hover:underline" to={`/incidents/${item.id}`}>
                      {item.incident_no}
                    </Link>
                  </td>
                  <td className="table-cell">{item.title}</td>
                  <td className="table-cell">{displayIncidentType(item.incident_type)}</td>
                  <td className="table-cell"><Badge value={item.severity} kind="severity" /></td>
                  <td className="table-cell"><Badge value={item.status} /></td>
                  <td className="table-cell">{item.occurrence_count}</td>
                  <td className="table-cell">{formatDateTime(item.sla_due_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-4 flex items-center justify-between text-sm">
        <span>共 {filtered.length} 条异常</span>
        <div className="flex items-center gap-2">
          <button className="border border-slate-300 px-3 py-1 disabled:opacity-40" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button>
          <span>第 {page} / {pages} 页</span>
          <button className="border border-slate-300 px-3 py-1 disabled:opacity-40" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>下一页</button>
        </div>
      </div>
    </Section>
  );
}
