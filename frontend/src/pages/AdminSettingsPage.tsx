import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { Card, ErrorBanner } from "../components/Common";
import type { SlaSetting } from "../api/types";

const PRIORITIES = ["critical", "high", "medium", "low"] as const;

export function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-settings"], queryFn: api.getSettings });
  const { data: models } = useQuery({ queryKey: ["admin-models-for-settings"], queryFn: api.listModels });

  const [medium, setMedium] = useState("0.40");
  const [high, setHigh] = useState("0.70");
  const [criticalAmount, setCriticalAmount] = useState("1000000");
  const [autoAssign, setAutoAssign] = useState(false);
  const [holdHighRisk, setHoldHighRisk] = useState(true);
  const [sla, setSla] = useState<Record<string, SlaSetting>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (data) {
      setMedium(String(data.risk_threshold_medium));
      setHigh(String(data.risk_threshold_high));
      setCriticalAmount(String(data.critical_amount_ngn));
      setAutoAssign(data.auto_assign);
      setHoldHighRisk(data.hold_high_risk);
      setSla(data.sla);
    }
  }, [data]);

  const activeModel = models?.find((m) => m.is_active);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateSettings({
        risk_threshold_medium: parseFloat(medium),
        risk_threshold_high: parseFloat(high),
        critical_amount_ngn: parseFloat(criticalAmount),
        auto_assign: autoAssign,
        hold_high_risk: holdHighRisk,
        sla,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
      setSuccess(true);
      setError(null);
    },
    onError: (e) => setError(errorMessage(e)),
  });

  if (isLoading) return <p className="text-gray-500">Loading settings...</p>;

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
      {error && <ErrorBanner message={error} />}
      {success && <div className="rounded border border-green-200 bg-green-50 p-3 text-sm text-green-700">Settings saved.</div>}

      <Card title="Risk thresholds">
        {activeModel?.metrics?.suggested_thresholds && (
          <p className="mb-3 text-xs text-gray-500">
            Model suggests: medium &ge; {activeModel.metrics.suggested_thresholds.suggested_medium_threshold?.toFixed(2)}, high &gt;{" "}
            {activeModel.metrics.suggested_thresholds.suggested_high_threshold?.toFixed(2)}
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Medium threshold</label>
            <input type="number" step="0.01" min="0" max="1" value={medium} onChange={(e) => setMedium(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">High threshold</label>
            <input type="number" step="0.01" min="0" max="1" value={high} onChange={(e) => setHigh(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
          </div>
        </div>
        <div className="mt-3">
          <label className="mb-1 block text-sm font-medium text-gray-700">Critical amount (NGN)</label>
          <input type="number" value={criticalAmount} onChange={(e) => setCriticalAmount(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
        </div>
      </Card>

      <Card title="SLA (minutes)">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-gray-500">
              <th className="pb-2">Priority</th>
              <th className="pb-2">Acknowledge</th>
              <th className="pb-2">Resolve</th>
            </tr>
          </thead>
          <tbody>
            {PRIORITIES.map((p) => (
              <tr key={p}>
                <td className="py-1 capitalize">{p}</td>
                <td className="py-1">
                  <input
                    type="number"
                    value={sla[p]?.ack_minutes ?? 0}
                    onChange={(e) => setSla({ ...sla, [p]: { ...sla[p], ack_minutes: parseInt(e.target.value) } })}
                    className="w-24 rounded border-gray-300 text-sm"
                  />
                </td>
                <td className="py-1">
                  <input
                    type="number"
                    value={sla[p]?.resolve_minutes ?? 0}
                    onChange={(e) => setSla({ ...sla, [p]: { ...sla[p], resolve_minutes: parseInt(e.target.value) } })}
                    className="w-24 rounded border-gray-300 text-sm"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Automation">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoAssign} onChange={(e) => setAutoAssign(e.target.checked)} />
          Auto-assign new high-risk cases to the least busy analyst
        </label>
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={holdHighRisk} onChange={(e) => setHoldHighRisk(e.target.checked)} />
          Hold high-risk transactions pending review
        </label>
      </Card>

      <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
        Save settings
      </button>
    </div>
  );
}
