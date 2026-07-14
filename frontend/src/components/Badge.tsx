import { displayBadgeValue, severityClass, statusClass } from "../lib/format";
import type { Severity } from "../types";

interface BadgeProps {
  value: string;
  kind?: "severity" | "status";
}

export function Badge({ value, kind = "status" }: BadgeProps) {
  const className = kind === "severity" ? severityClass(value as Severity) : statusClass(value);
  return <span className={`inline-flex whitespace-nowrap border px-2 py-0.5 text-xs font-semibold ${className}`}>{displayBadgeValue(value, kind)}</span>;
}
