import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as api from "../api/endpoints";
import { RiskBadge } from "../components/Badges";
import { EmptyRow, LoadingRow, Pagination } from "../components/Common";
import { formatDateTime, formatMoney } from "../components/format";

export function TransactionsPage() {
  const [accountNumber, setAccountNumber] = useState("");
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["transactions", accountNumber, channel, status, page],
    queryFn: () =>
      api.listTransactions({
        account_number: accountNumber || undefined,
        channel: channel || undefined,
        status: status || undefined,
        page,
        page_size: pageSize,
      }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Transactions</h1>

      <div className="flex flex-wrap gap-3 text-sm">
        <input
          value={accountNumber}
          onChange={(e) => { setAccountNumber(e.target.value); setPage(1); }}
          placeholder="Account number"
          className="rounded border-gray-300 text-sm"
        />
        <select value={channel} onChange={(e) => { setChannel(e.target.value); setPage(1); }} className="rounded border-gray-300 text-sm">
          <option value="">All channels</option>
          {["NIP", "MOBILE", "USSD", "INTERNET", "POS", "ATM"].map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="rounded border-gray-300 text-sm">
          <option value="">All statuses</option>
          {["APPROVED", "HELD", "DECLINED", "HISTORICAL"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded border border-gray-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Time</th>
              <th className="p-3">Ref</th>
              <th className="p-3">Account</th>
              <th className="p-3">Channel</th>
              <th className="p-3">Amount</th>
              <th className="p-3">Band</th>
              <th className="p-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && <LoadingRow colSpan={7} />}
            {!isLoading && (data?.items.length ?? 0) === 0 && <EmptyRow colSpan={7} />}
            {data?.items.map((t) => (
              <tr key={t.txn_id} className="hover:bg-gray-50">
                <td className="p-3">
                  <Link to={`/transactions/${t.txn_id}`} className="text-blue-600 hover:underline">
                    {formatDateTime(t.txn_time)}
                  </Link>
                </td>
                <td className="p-3 font-mono text-xs">{t.txn_ref}</td>
                <td className="p-3">{t.account_number_masked}</td>
                <td className="p-3">{t.channel}</td>
                <td className="p-3">{formatMoney(t.amount)}</td>
                <td className="p-3"><RiskBadge band={t.risk_band} /></td>
                <td className="p-3">{t.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={page} pageSize={pageSize} total={data.total} onChange={setPage} />}
      </div>
    </div>
  );
}
