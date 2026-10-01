import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { EmptyRow, LoadingRow, Pagination } from "../components/Common";
import { formatDateTime } from "../components/format";

export function AdminAuditPage() {
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const pageSize = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", action, entity, page],
    queryFn: () => api.listAuditLogs({ action: action || undefined, entity: entity || undefined, page, page_size: pageSize }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Audit log</h1>

      <div className="flex flex-wrap gap-3 text-sm">
        <input value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} placeholder="Filter by action" className="rounded border-gray-300 text-sm" />
        <input value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1); }} placeholder="Filter by entity" className="rounded border-gray-300 text-sm" />
      </div>

      <div className="overflow-x-auto rounded border border-gray-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Time</th>
              <th className="p-3">Actor</th>
              <th className="p-3">Action</th>
              <th className="p-3">Entity</th>
              <th className="p-3">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && <LoadingRow colSpan={5} />}
            {!isLoading && (data?.items.length ?? 0) === 0 && <EmptyRow colSpan={5} />}
            {data?.items.map((log) => (
              <tr key={log.log_id}>
                <td className="p-3">{formatDateTime(log.timestamp)}</td>
                <td className="p-3">{log.actor}</td>
                <td className="p-3">{log.action}</td>
                <td className="p-3">{log.entity} / {log.entity_id.slice(0, 8)}</td>
                <td className="p-3">
                  <button onClick={() => setExpanded(expanded === log.log_id ? null : log.log_id)} className="text-blue-600 hover:underline">
                    {expanded === log.log_id ? "Hide" : "Show"}
                  </button>
                  {expanded === log.log_id && (
                    <pre className="mt-2 max-w-md overflow-x-auto rounded bg-gray-50 p-2 text-xs">{JSON.stringify(log.details, null, 2)}</pre>
                  )}
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
