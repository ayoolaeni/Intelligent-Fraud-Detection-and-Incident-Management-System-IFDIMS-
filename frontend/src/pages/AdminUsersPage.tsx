import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { EmptyRow, ErrorBanner, LoadingRow, Modal } from "../components/Common";
import { formatDateTime } from "../components/format";

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-users"], queryFn: () => api.listUsers({ page_size: 100 }) });
  const [showCreate, setShowCreate] = useState(false);
  const [tempPasswordResult, setTempPasswordResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("analyst");
  const [tempPassword, setTempPassword] = useState("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });

  const createMutation = useMutation({
    mutationFn: () => api.createUser({ full_name: fullName, email, role, temporary_password: tempPassword }),
    onSuccess: () => {
      invalidate();
      setShowCreate(false);
      setFullName("");
      setEmail("");
      setTempPassword("");
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => api.updateUser(id, { is_active }),
    onSuccess: invalidate,
    onError: (e) => setError(errorMessage(e)),
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (id: string) => api.resetUserPassword(id),
    onSuccess: (result) => setTempPasswordResult(result.temporary_password),
    onError: (e) => setError(errorMessage(e)),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Users</h1>
        <button onClick={() => setShowCreate(true)} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
          New user
        </button>
      </div>
      {error && <ErrorBanner message={error} />}

      <div className="overflow-x-auto rounded border border-gray-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Name</th>
              <th className="p-3">Email</th>
              <th className="p-3">Role</th>
              <th className="p-3">Status</th>
              <th className="p-3">Last login</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading && <LoadingRow colSpan={6} />}
            {!isLoading && (data?.items.length ?? 0) === 0 && <EmptyRow colSpan={6} />}
            {data?.items.map((u) => (
              <tr key={u.user_id}>
                <td className="p-3">{u.full_name}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3 capitalize">{u.role}</td>
                <td className="p-3">{u.is_active ? "Active" : "Inactive"}</td>
                <td className="p-3">{u.last_login_at ? formatDateTime(u.last_login_at) : "Never"}</td>
                <td className="p-3">
                  <div className="flex gap-2 text-xs">
                    <button
                      onClick={() => toggleActiveMutation.mutate({ id: u.user_id, is_active: !u.is_active })}
                      className="text-blue-600 hover:underline"
                    >
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button onClick={() => resetPasswordMutation.mutate(u.user_id)} className="text-blue-600 hover:underline">
                      Reset password
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <Modal title="New user" onClose={() => setShowCreate(false)}>
          <form
            onSubmit={(e) => { e.preventDefault(); createMutation.mutate(); }}
            className="space-y-3"
          >
            <input required placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
            <input required type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
            <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full rounded border-gray-300 text-sm">
              <option value="analyst">Analyst</option>
              <option value="supervisor">Supervisor</option>
              <option value="admin">Admin</option>
            </select>
            <input required placeholder="Temporary password" value={tempPassword} onChange={(e) => setTempPassword(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
            <button type="submit" disabled={createMutation.isPending} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
              Create
            </button>
          </form>
        </Modal>
      )}

      {tempPasswordResult && (
        <Modal title="Temporary password" onClose={() => setTempPasswordResult(null)}>
          <p className="text-sm text-gray-600">Share this with the user; it won't be shown again:</p>
          <p className="mt-2 rounded bg-gray-100 p-2 font-mono text-sm">{tempPasswordResult}</p>
        </Modal>
      )}
    </div>
  );
}
