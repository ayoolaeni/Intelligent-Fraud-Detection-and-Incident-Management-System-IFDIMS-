import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as api from "../api/endpoints";
import { RiskBadge } from "../components/Badges";
import { EmptyRow, LoadingRow, Pagination } from "../components/Common";
import { formatDateTime, formatMoney } from "../components/format";

export function AlertQueuePage() {
  const [status, setStatus] = useState("OPEN");
  const [severity, setSeverity] = useState("");
  const [sort, setSort] = useState("created_at");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", status, severity, sort, page],
    queryFn: () => api.listAlerts({ status: status || undefined, severity: severity || undefined, sort, page, page_size: pageSize }),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Alert queue</h1>

      <div className="flex flex-wrap gap-3 text-sm">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="rounded border-gray-300 text-sm">
          <option value="OPEN">Open</option>
          <option value="DISMISSED">Dismissed</option>
          <option value="CASE_OPENED">Case opened</option>
          <option value="">All statuses</option>
        </select>
        <select value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }} className="rounded border-gray-300 text-sm">
          <option value="">All severities</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded border-gray-300 text-sm">
          <option value="created_at">Sort by time</option>
          <option value="fraud_score">Sort by score</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded border border-gray-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Time</th>
              <th className="p-3">Account</th>
              <th className="p-3">Channel</th>
              <th className="p-3">Amount</th>
              <th className="p-3">Score</th>
              <th className="p-3">Band</th>
              <th className="p-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && <LoadingRow colSpan={7} />}
            {!isLoading && (data?.items.length ?? 0) === 0 && <EmptyRow colSpan={7} />}
            {data?.items.map((a) => (
              <tr
                key={a.alert_id}
                className={`hover:bg-gray-50 ${a.severity === "high" ? "bg-red-50/40" : ""}`}
              >
                <td className="p-3">
                  <Link to={`/alerts/${a.alert_id}`} className="text-blue-600 hover:underline">
                    {formatDateTime(a.created_at)}
                  </Link>
                </td>
                <td className="p-3">{a.account_number_masked}</td>
                <td className="p-3">{a.channel}</td>
                <td className="p-3">{formatMoney(a.amount)}</td>
                <td className="p-3">{a.fraud_score.toFixed(3)}</td>
                <td className="p-3">
                  <RiskBadge band={a.risk_band} />
                </td>
                <td className="p-3">{a.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={page} pageSize={pageSize} total={data.total} onChange={setPage} />}
      </div>
    </div>
  );
}
