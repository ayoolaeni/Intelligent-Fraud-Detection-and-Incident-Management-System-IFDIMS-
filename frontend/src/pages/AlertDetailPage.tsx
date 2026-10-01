import React, { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { RiskBadge } from "../components/Badges";
import { Card, ErrorBanner, Modal } from "../components/Common";
import { ShapChart } from "../components/ShapChart";
import { formatDateTime, formatMoney } from "../components/format";

export function AlertDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showDismiss, setShowDismiss] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["alert", id],
    queryFn: () => api.getAlert(id!),
    enabled: !!id,
  });

  const dismissMutation = useMutation({
    mutationFn: () => api.dismissAlert(id!, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert", id] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setShowDismiss(false);
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const openCaseMutation = useMutation({
    mutationFn: () => api.openCaseFromAlert(id!),
    onSuccess: (result) => navigate(`/cases/${result.case_id}`),
    onError: (e) => setError(errorMessage(e)),
  });

  if (isLoading || !data) return <p className="text-gray-500">Loading alert...</p>;

  const { alert, txn, top_factors, customer, recent_transactions } = data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Alert detail</h1>
        <div className="flex gap-2">
          {alert.status === "OPEN" && (
            <>
              <button onClick={() => setShowDismiss(true)} className="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50">
                Dismiss (false positive)
              </button>
              {alert.severity === "medium" && (
                <button
                  onClick={() => openCaseMutation.mutate()}
                  className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                >
                  Open case
                </button>
              )}
            </>
          )}
          {alert.case_id && (
            <Link to={`/cases/${alert.case_id}`} className="rounded bg-gray-800 px-3 py-1.5 text-sm text-white hover:bg-gray-700">
              Go to case
            </Link>
          )}
        </div>
      </div>

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Transaction">
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Account</dt><dd>{alert.account_number_masked}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Channel</dt><dd>{txn.channel} / {txn.txn_type}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Amount</dt><dd>{formatMoney(txn.amount)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Time</dt><dd>{formatDateTime(txn.txn_time)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Location</dt><dd>{txn.location}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Status</dt><dd>{txn.status}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Band</dt><dd><RiskBadge band={alert.risk_band} /></dd></div>
          </dl>
        </Card>

        <Card title="Customer">
          {customer ? (
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Name</dt><dd>{customer.full_name}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Phone</dt><dd>{customer.phone_masked}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Risk profile</dt><dd>{customer.risk_profile}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Account age</dt><dd>{Math.round(customer.account_age_days)} days</dd></div>
            </dl>
          ) : (
            <p className="text-sm text-gray-500">No customer profile.</p>
          )}
        </Card>

        <Card title="Why this was flagged">
          <ShapChart factors={top_factors} />
        </Card>
      </div>

      <Card title="Recent account activity">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-xs uppercase text-gray-500">
              <tr>
                <th className="p-2">Time</th>
                <th className="p-2">Channel</th>
                <th className="p-2">Amount</th>
                <th className="p-2">Band</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {recent_transactions.map((t) => (
                <tr key={t.txn_id}>
                  <td className="p-2">{formatDateTime(t.txn_time)}</td>
                  <td className="p-2">{t.channel}</td>
                  <td className="p-2">{formatMoney(t.amount)}</td>
                  <td className="p-2"><RiskBadge band={t.risk_band} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {showDismiss && (
        <Modal title="Dismiss alert" onClose={() => setShowDismiss(false)}>
          <textarea
            className="mb-3 w-full rounded border border-gray-300 p-2 text-sm"
            rows={3}
            placeholder="Reason for dismissing this alert"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowDismiss(false)} className="rounded border px-3 py-1.5 text-sm">Cancel</button>
            <button
              onClick={() => dismissMutation.mutate()}
              disabled={!reason || dismissMutation.isPending}
              className="rounded bg-red-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Dismiss
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
