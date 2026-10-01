import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Card, ErrorBanner } from "../components/Common";

export function AccountPage() {
  const { user } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: () => {
      setSuccess(true);
      setError(null);
      setCurrent("");
      setNext("");
    },
    onError: (e) => setError(errorMessage(e)),
  });

  return (
    <div className="max-w-md space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">My account</h1>
      <Card title="Profile">
        <dl className="space-y-1 text-sm">
          <div className="flex justify-between"><dt className="text-gray-500">Name</dt><dd>{user?.full_name}</dd></div>
          <div className="flex justify-between"><dt className="text-gray-500">Email</dt><dd>{user?.email}</dd></div>
          <div className="flex justify-between"><dt className="text-gray-500">Role</dt><dd className="capitalize">{user?.role}</dd></div>
        </dl>
      </Card>

      <Card title="Change password">
        {error && <div className="mb-3"><ErrorBanner message={error} /></div>}
        {success && <div className="mb-3 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-700">Password changed.</div>}
        <form onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }} className="space-y-3">
          <input type="password" required placeholder="Current password" value={current} onChange={(e) => setCurrent(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
          <input type="password" required placeholder="New password (min 10 chars, letters + digits)" value={next} onChange={(e) => setNext(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
          <button type="submit" disabled={mutation.isPending} className="rounded bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50">
            Change password
          </button>
        </form>
      </Card>
    </div>
  );
}
