import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { EmptyRow, ErrorBanner, LoadingRow, Modal } from "../components/Common";
import { formatDateTime } from "../components/format";

export function AdminModelsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-models"], queryFn: api.listModels });
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activateMutation = useMutation({
    mutationFn: (id: string) => api.activateModel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
      setConfirmId(null);
    },
    onError: (e) => setError(errorMessage(e)),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Models</h1>
      {error && <ErrorBanner message={error} />}

      <div className="overflow-x-auto rounded border border-gray-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Version</th>
              <th className="p-3">Algorithm</th>
              <th className="p-3">Test PR-AUC</th>
              <th className="p-3">Recall</th>
              <th className="p-3">Precision</th>
              <th className="p-3">Latency (ms)</th>
              <th className="p-3">Deployed</th>
              <th className="p-3">Status</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && <LoadingRow colSpan={9} />}
            {!isLoading && (data?.length ?? 0) === 0 && <EmptyRow colSpan={9} />}
            {data?.map((m) => {
              const test = m.metrics?.test_metrics ?? {};
              return (
                <tr key={m.model_id} className={m.is_active ? "bg-blue-50/40" : ""}>
                  <td className="p-3 font-mono text-xs">{m.version}</td>
                  <td className="p-3">{m.algorithm}</td>
                  <td className="p-3">{test.pr_auc?.toFixed(3) ?? "n/a"}</td>
                  <td className="p-3">{test.recall?.toFixed(3) ?? "n/a"}</td>
                  <td className="p-3">{test.precision?.toFixed(3) ?? "n/a"}</td>
                  <td className="p-3">{m.metrics?.latency_ms_per_prediction?.toFixed(1) ?? "n/a"}</td>
                  <td className="p-3">{m.deployed_on ? formatDateTime(m.deployed_on) : "-"}</td>
                  <td className="p-3">{m.is_active ? <span className="font-medium text-green-700">Active</span> : "Inactive"}</td>
                  <td className="p-3">
                    {!m.is_active && (
                      <button onClick={() => setConfirmId(m.model_id)} className="text-blue-600 hover:underline">
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {confirmId && (
        <Modal title="Activate model" onClose={() => setConfirmId(null)}>
          <p className="mb-4 text-sm text-gray-600">
            This will hot-swap the live scoring model. A smoke test runs first; if it fails, nothing changes.
          </p>
          <div className="flex justify-end gap-2">
            <button onClick={() => setConfirmId(null)} className="rounded border px-3 py-1.5 text-sm">Cancel</button>
            <button
              onClick={() => activateMutation.mutate(confirmId)}
              disabled={activateMutation.isPending}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Activate
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
