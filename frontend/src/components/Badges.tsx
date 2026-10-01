import React from "react";

const RISK_STYLES: Record<string, string> = {
  low: "bg-green-100 text-green-800 border-green-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  high: "bg-red-100 text-red-800 border-red-300",
};

export function RiskBadge({ band }: { band: string | null }) {
  if (!band) return <span className="text-gray-400">&ndash;</span>;
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium uppercase ${RISK_STYLES[band] ?? ""}`}>
      {band}
    </span>
  );
}

const PRIORITY_STYLES: Record<string, string> = {
  critical: "bg-red-900 text-white border-red-900",
  high: "bg-red-100 text-red-800 border-red-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  low: "bg-gray-100 text-gray-700 border-gray-300",
};

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium uppercase ${PRIORITY_STYLES[priority] ?? ""}`}>
      {priority}
    </span>
  );
}

const SLA_STYLES: Record<string, string> = {
  ok: "bg-gray-100 text-gray-700",
  due_soon: "bg-amber-100 text-amber-800",
  breached: "bg-red-100 text-red-800",
};

export function SlaBadge({ state, dueAt }: { state: string; dueAt?: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${SLA_STYLES[state] ?? ""}`}>
      {state.replace("_", " ")}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-block rounded border border-gray-300 bg-white px-2 py-0.5 text-xs font-medium text-gray-700">
      {status.replace(/_/g, " ")}
    </span>
  );
}
