import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import * as api from "../api/endpoints";
import { Card } from "../components/Common";
import { formatMoney } from "../components/format";

function Kpi({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

export function OverviewPage() {
  const { data: summary, isLoading } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: api.getDashboardSummary,
    refetchInterval: 30000,
  });
  const { data: trends } = useQuery({
    queryKey: ["dashboard-trends"],
    queryFn: () => api.getDashboardTrends(30),
    refetchInterval: 30000,
  });
  const { data: dueSoonCases } = useQuery({
    queryKey: ["cases-due-review"],
    queryFn: () => api.listCases({ page: 1, page_size: 10 }),
  });

  if (isLoading || !summary) return <p className="text-gray-500">Loading dashboard...</p>;

  const channelData = Object.entries(trends?.by_channel ?? {}).map(([channel, sev]) => ({
    channel,
    medium: sev.medium ?? 0,
    high: sev.high ?? 0,
  }));

  const flagged = (dueSoonCases?.items ?? []).filter((c) => c.sla_state !== "ok");

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Overview</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Kpi label="Open medium alerts" value={summary.open_alerts.medium ?? 0} />
        <Kpi label="Open high alerts" value={summary.open_alerts.high ?? 0} />
        <Kpi label="Cases breaching SLA" value={summary.cases_breaching_sla} />
        <Kpi label="Cases due soon" value={summary.cases_due_soon} />
        <Kpi label="Transactions today" value={summary.transactions_today} />
        <Kpi label="Held transactions" value={summary.held_transactions} />
        <Kpi label="Confirmed fraud (30d)" value={formatMoney(summary.confirmed_fraud_value_30d)} />
        <Kpi label="False positive rate (30d)" value={`${(summary.false_positive_rate_30d * 100).toFixed(1)}%`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Alerts and confirmed fraud (30 days)">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trends?.daily ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line type="monotone" dataKey="alerts_medium" stroke="#d97706" name="Medium alerts" dot={false} />
              <Line type="monotone" dataKey="alerts_high" stroke="#dc2626" name="High alerts" dot={false} />
              <Line type="monotone" dataKey="confirmed_fraud_count" stroke="#1f2937" name="Confirmed fraud" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Alerts by channel (30 days)">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={channelData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="channel" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="medium" fill="#d97706" name="Medium" />
              <Bar dataKey="high" fill="#dc2626" name="High" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Cases due soon / breached">
        {flagged.length === 0 ? (
          <p className="text-sm text-gray-500">No cases due soon or breaching SLA.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {flagged.map((c) => (
              <li key={c.case_id} className="flex items-center justify-between py-2 text-sm">
                <Link to={`/cases/${c.case_id}`} className="text-blue-600 hover:underline">
                  {c.case_number} &middot; {c.title}
                </Link>
                <span className={c.sla_state === "breached" ? "text-red-600" : "text-amber-600"}>
                  {c.sla_state.replace("_", " ")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
