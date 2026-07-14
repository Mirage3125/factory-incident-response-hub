import { AlertTriangle, Loader2 } from "lucide-react";
import { ApiError } from "../lib/api";
import { formatErrorMessage } from "../lib/format";

export function LoadingState({ label = "加载中" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}

export function EmptyState({ label }: { label: string }) {
  return <div className="border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">{label}</div>;
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? formatErrorMessage(new Error(String(error.detail))) : formatErrorMessage(error);
  return (
    <div role="alert" className="flex items-start gap-2 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
