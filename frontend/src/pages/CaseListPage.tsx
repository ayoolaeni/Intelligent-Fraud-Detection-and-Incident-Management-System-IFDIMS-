import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import * as api from "../api/endpoints";
import { PriorityBadge, SlaBadge, StatusBadge } from "../components/Badges";
import { EmptyRow, LoadingRow, Pagination } from "../components/Common";
import { formatCountdown, formatDateTime, formatMoney } from "../components/format";

type Tab = "mine" | "unassigned" | "all" | "escalated";

export function CaseListPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>(user?.role === "supervisor" ? "all" : "mine");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const params: Record<string, any> = { page, page_size: pageSize };
  if (tab === "mine") params.assigned_to = "me";
  if (tab === "unassigned") params.assigned_to = "unassigned"; // handled client-side below
  if (tab === "escalated") params.status = "ESCALATED";
  if (q) params.q = q;

  const { data, isLoading } = useQuery({
    queryKey: ["cases", tab, q, page],
    queryFn: () => api.listCases(tab === "unassigned" ? { page, page_size: pageSize, q: q || undefined } : params),
  });

  const items = tab === "unassigned" ? (data?.items ?? []).filter((c) => !c.assigned_to) : data?.items ?? [];

  const tabs: { key: Tab; label: string }[] = [
    { key: "mine", label: "My cases" },
    { key: "unassigned", label: "Unassigned" },
    ...(user?.role === "supervisor" ? [{ key: "all" as Tab, label: "All" }] : []),
    { key: "escalated", label: "Escalated" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Cases</h1>
        {user?.role !== "admin" && (
          <Link to="/cases/new" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
            New case
          </Link>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 rounded border border-gray-200 bg-white p-1 text-sm">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setPage(1); }}
              className={`rounded px-3 py-1 ${tab === t.key ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          placeholder="Search case number, title, account..."
          className="w-64 rounded border-gray-300 text-sm"
        />
      </div>

      <div className="overflow-x-auto rounded border border-gray-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Case</th>
              <th className="p-3">Priority</th>
              <th className="p-3">Status</th>
              <th className="p-3">Assignee</th>
              <th className="p-3">Amount at risk</th>
              <th className="p-3">Opened</th>
              <th className="p-3">SLA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && <LoadingRow colSpan={7} />}
            {!isLoading && items.length === 0 && <EmptyRow colSpan={7} />}
            {items.map((c) => (
              <tr key={c.case_id} className="hover:bg-gray-50">
                <td className="p-3">
                  <Link to={`/cases/${c.case_id}`} className="text-blue-600 hover:underline">
                    {c.case_number}
                  </Link>
                  <div className="text-xs text-gray-500">{c.title}</div>
                </td>
                <td className="p-3"><PriorityBadge priority={c.priority} /></td>
                <td className="p-3"><StatusBadge status={c.status} /></td>
                <td className="p-3">{c.assigned_to_name ?? "Unassigned"}</td>
                <td className="p-3">{formatMoney(c.amount_at_risk)}</td>
                <td className="p-3">{formatDateTime(c.opened_at)}</td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <SlaBadge state={c.sla_state} />
                    {c.status !== "RESOLVED" && c.status !== "CLOSED" && (
                      <span className="text-xs text-gray-400">{formatCountdown(c.resolve_due_at)}</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={page} pageSize={pageSize} total={data.total} onChange={setPage} />}
      </div>
    </div>
  );
}
