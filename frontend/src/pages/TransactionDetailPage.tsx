import React from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { RiskBadge } from "../components/Badges";
import { Card } from "../components/Common";
import { ShapChart } from "../components/ShapChart";
import { formatDateTime, formatMoney } from "../components/format";

export function TransactionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({ queryKey: ["transaction", id], queryFn: () => api.getTransaction(id!), enabled: !!id });

  if (isLoading || !data) return <p className="text-gray-500">Loading transaction...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Transaction {data.txn.txn_ref}</h1>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Details">
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Account</dt><dd>{data.txn.account_number_masked}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Channel</dt><dd>{data.txn.channel} / {data.txn.txn_type}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Amount</dt><dd>{formatMoney(data.txn.amount)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Time</dt><dd>{formatDateTime(data.txn.txn_time)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Location</dt><dd>{data.txn.location}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Status</dt><dd>{data.txn.status}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Band</dt><dd><RiskBadge band={data.txn.risk_band} /></dd></div>
          </dl>
          <div className="mt-3 flex gap-3 text-sm">
            {data.alert_id && <Link to={`/alerts/${data.alert_id}`} className="text-blue-600 hover:underline">View alert</Link>}
            {data.case_id && <Link to={`/cases/${data.case_id}`} className="text-blue-600 hover:underline">View case {data.case_number}</Link>}
          </div>
        </Card>

        <Card title="Customer">
          {data.customer ? (
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Name</dt><dd>{data.customer.full_name}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Phone</dt><dd>{data.customer.phone_masked}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Risk profile</dt><dd>{data.customer.risk_profile}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Account age</dt><dd>{Math.round(data.customer.account_age_days)} days</dd></div>
            </dl>
          ) : (
            <p className="text-sm text-gray-500">n/a</p>
          )}
        </Card>

        <Card title="Explanation">
          {data.prediction ? <ShapChart factors={data.prediction.top_factors} /> : <p className="text-sm text-gray-500">Not scored.</p>}
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
              {data.recent_transactions.map((t) => (
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
    </div>
  );
}
