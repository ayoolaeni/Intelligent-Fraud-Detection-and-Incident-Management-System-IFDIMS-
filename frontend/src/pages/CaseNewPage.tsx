import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { ErrorBanner } from "../components/Common";

export function CaseNewPage() {
  const navigate = useNavigate();
  const [source, setSource] = useState("CUSTOMER_REPORT");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [amount, setAmount] = useState("0");
  const [priority, setPriority] = useState("medium");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.createCase({
        source,
        title,
        description,
        account_number: accountNumber || undefined,
        amount_at_risk: amount,
        priority,
      }),
    onSuccess: (c) => navigate(`/cases/${c.case_id}`),
    onError: (e) => setError(errorMessage(e)),
  });

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">New case</h1>
      {error && <ErrorBanner message={error} />}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
        className="space-y-4 rounded border border-gray-200 bg-white p-5"
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Source</label>
          <select value={source} onChange={(e) => setSource(e.target.value)} className="w-full rounded border-gray-300 text-sm">
            <option value="CUSTOMER_REPORT">Customer report</option>
            <option value="MANUAL">Manual</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Title</label>
          <input required value={title} onChange={(e) => setTitle(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
          <textarea required rows={4} value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Account number (optional)</label>
          <input value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Amount at risk (NGN)</label>
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)} className="w-full rounded border-gray-300 text-sm">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Create case
        </button>
      </form>
    </div>
  );
}
