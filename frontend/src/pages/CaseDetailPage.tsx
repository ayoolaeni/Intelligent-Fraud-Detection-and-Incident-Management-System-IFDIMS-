import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/endpoints";
import { errorMessage } from "../api/client";
import { downloadAuthenticated } from "../api/download";
import { PriorityBadge, SlaBadge, StatusBadge } from "../components/Badges";
import { Card, ErrorBanner, Modal } from "../components/Common";
import { ShapChart } from "../components/ShapChart";
import { formatCountdown, formatDateTime, formatMoney } from "../components/format";
import { useAuth } from "../auth/AuthContext";

const FRAUD_TYPES = ["SOCIAL_ENGINEERING", "ACCOUNT_TAKEOVER", "SIM_SWAP", "CARD_FRAUD", "INSIDER", "IDENTITY_FRAUD", "OTHER"];

type TransitionModalState = { to_status: string } | null;

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"notes" | "attachments" | "history">("notes");
  const [transitionModal, setTransitionModal] = useState<TransitionModalState>(null);
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("confirmed_fraud");
  const [fraudType, setFraudType] = useState(FRAUD_TYPES[0]);
  const [amountRecovered, setAmountRecovered] = useState("0");
  const [showAssign, setShowAssign] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [releaseReason, setReleaseReason] = useState("");
  const [showRelease, setShowRelease] = useState<"release" | "decline" | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["case", id], queryFn: () => api.getCase(id!), enabled: !!id });
  const { data: txnDetail } = useQuery({
    queryKey: ["txn-for-case", data?.txn_id],
    queryFn: () => api.getTransaction(data!.txn_id!),
    enabled: !!data?.txn_id,
  });
  const { data: assignable } = useQuery({
    queryKey: ["assignable-users"],
    queryFn: api.listAssignableUsers,
    enabled: !!data?.can_assign,
  });
  const { data: history } = useQuery({
    queryKey: ["case-history", id],
    queryFn: () => api.getCaseHistory(id!),
    enabled: tab === "history",
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["case", id] });
    queryClient.invalidateQueries({ queryKey: ["case-history", id] });
  };

  const transitionMutation = useMutation({
    mutationFn: (payload: Record<string, any>) => api.transitionCase(id!, payload),
    onSuccess: () => {
      invalidate();
      setTransitionModal(null);
      setNote("");
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const assignMutation = useMutation({
    mutationFn: (userId: string) => api.assignCase(id!, userId),
    onSuccess: () => {
      invalidate();
      setShowAssign(false);
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const noteMutation = useMutation({
    mutationFn: () => api.addCaseNote(id!, newNote),
    onSuccess: () => {
      invalidate();
      setNewNote("");
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadAttachment(id!, file),
    onSuccess: invalidate,
    onError: (e) => setError(errorMessage(e)),
  });

  const releaseMutation = useMutation({
    mutationFn: () =>
      showRelease === "release" ? api.releaseTransaction(data!.txn_id!, releaseReason) : api.declineTransaction(data!.txn_id!, releaseReason),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["txn-for-case"] });
      setShowRelease(null);
      setReleaseReason("");
    },
    onError: (e) => setError(errorMessage(e)),
  });

  if (isLoading || !data) return <p className="text-gray-500">Loading case...</p>;

  const c = data.case;
  const requiresOutcome = transitionModal?.to_status === "RESOLVED";

  const submitTransition = () => {
    const payload: Record<string, any> = { to_status: transitionModal!.to_status, note };
    if (requiresOutcome) {
      payload.outcome = outcome;
      if (outcome === "confirmed_fraud") payload.fraud_type = fraudType;
      payload.amount_recovered = amountRecovered;
    }
    transitionMutation.mutate(payload);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {c.case_number} &middot; {c.title}
          </h1>
          <div className="mt-1 flex items-center gap-2">
            <PriorityBadge priority={c.priority} />
            <StatusBadge status={c.status} />
            {c.status !== "RESOLVED" && c.status !== "CLOSED" && (
              <>
                <SlaBadge state={c.sla_state} />
                <span className="text-xs text-gray-400">resolve due in {formatCountdown(c.resolve_due_at)}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {data.can_assign && (
            <button onClick={() => setShowAssign(true)} className="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50">
              {c.assigned_to ? "Reassign" : "Assign"}
            </button>
          )}
          {data.allowed_transitions.map((status) => (
            <button
              key={status}
              onClick={() => setTransitionModal({ to_status: status })}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
            >
              {status.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Details">
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Account</dt><dd>{data.account_number_masked ?? "n/a"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Amount at risk</dt><dd>{formatMoney(c.amount_at_risk)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Amount recovered</dt><dd>{formatMoney(c.amount_recovered)}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Assignee</dt><dd>{c.assigned_to_name ?? "Unassigned"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Outcome</dt><dd>{c.outcome ?? "pending"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Fraud type</dt><dd>{data.fraud_type ?? "n/a"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Opened</dt><dd>{formatDateTime(c.opened_at)}</dd></div>
          </dl>
          <p className="mt-3 whitespace-pre-wrap text-sm text-gray-600">{data.description}</p>

          {data.can_release_decline && txnDetail?.txn.status === "HELD" && (
            <div className="mt-4 flex gap-2">
              <button onClick={() => setShowRelease("release")} className="rounded border border-green-300 px-3 py-1.5 text-sm text-green-700 hover:bg-green-50">
                Release transaction
              </button>
              <button onClick={() => setShowRelease("decline")} className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50">
                Decline transaction
              </button>
            </div>
          )}
        </Card>

        <Card title="Linked transaction">
          {txnDetail ? (
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Channel</dt><dd>{txnDetail.txn.channel} / {txnDetail.txn.txn_type}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Amount</dt><dd>{formatMoney(txnDetail.txn.amount)}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Score</dt><dd>{txnDetail.prediction?.fraud_score.toFixed(3) ?? "n/a"}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Status</dt><dd>{txnDetail.txn.status}</dd></div>
            </dl>
          ) : (
            <p className="text-sm text-gray-500">No linked transaction.</p>
          )}
        </Card>

        <Card title="Why this was flagged">
          {txnDetail?.prediction ? <ShapChart factors={txnDetail.prediction.top_factors} /> : <p className="text-sm text-gray-500">n/a</p>}
        </Card>
      </div>

      <div>
        <div className="mb-2 flex gap-1 rounded border border-gray-200 bg-white p-1 text-sm w-fit">
          {(["notes", "attachments", "history"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded px-3 py-1 capitalize ${tab === t ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "notes" && (
          <Card>
            <div className="mb-3 flex gap-2">
              <input value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder="Add a note" className="flex-1 rounded border-gray-300 text-sm" />
              <button onClick={() => noteMutation.mutate()} disabled={!newNote} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
                Add
              </button>
            </div>
            <ul className="space-y-3">
              {data.notes.map((n) => (
                <li key={n.note_id} className="border-l-2 border-gray-200 pl-3 text-sm">
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>{n.user_name ?? "System"}</span>
                    <span>&middot;</span>
                    <span>{formatDateTime(n.created_at)}</span>
                    <span className="rounded bg-gray-100 px-1.5">{n.note_type}</span>
                  </div>
                  <p className="text-gray-800">{n.note}</p>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {tab === "attachments" && (
          <Card>
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadMutation.mutate(file);
              }}
              className="mb-3 text-sm"
            />
            <ul className="divide-y divide-gray-100 text-sm">
              {data.attachments.length === 0 && <li className="py-2 text-gray-400">No attachments</li>}
              {data.attachments.map((a) => (
                <li key={a.attachment_id} className="flex items-center justify-between py-2">
                  <span>{a.file_name}</span>
                  <a
                    className="text-blue-600 hover:underline"
                    href={api.attachmentDownloadUrl(c.case_id, a.attachment_id)}
                    onClick={(e) => {
                      e.preventDefault();
                      downloadAuthenticated(api.attachmentDownloadUrl(c.case_id, a.attachment_id), a.file_name);
                    }}
                  >
                    Download
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {tab === "history" && (
          <Card>
            <ul className="space-y-2 text-sm">
              {(history ?? []).map((h) => (
                <li key={h.log_id} className="border-l-2 border-gray-200 pl-3">
                  <div className="text-xs text-gray-400">
                    {h.actor} &middot; {formatDateTime(h.timestamp)}
                  </div>
                  <div className="font-medium text-gray-800">{h.action}</div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {transitionModal && (
        <Modal title={`Move to ${transitionModal.to_status.replace(/_/g, " ")}`} onClose={() => setTransitionModal(null)}>
          <textarea
            className="mb-3 w-full rounded border border-gray-300 p-2 text-sm"
            rows={3}
            placeholder="Note (required for most transitions)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          {requiresOutcome && (
            <div className="mb-3 space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Outcome</label>
                <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className="w-full rounded border-gray-300 text-sm">
                  <option value="confirmed_fraud">Confirmed fraud</option>
                  <option value="false_positive">False positive</option>
                </select>
              </div>
              {outcome === "confirmed_fraud" && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Fraud type</label>
                  <select value={fraudType} onChange={(e) => setFraudType(e.target.value)} className="w-full rounded border-gray-300 text-sm">
                    {FRAUD_TYPES.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Amount recovered (NGN)</label>
                <input type="number" step="0.01" value={amountRecovered} onChange={(e) => setAmountRecovered(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <button onClick={() => setTransitionModal(null)} className="rounded border px-3 py-1.5 text-sm">Cancel</button>
            <button onClick={submitTransition} disabled={transitionMutation.isPending} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
              Confirm
            </button>
          </div>
        </Modal>
      )}

      {showAssign && (
        <Modal title="Assign case" onClose={() => setShowAssign(false)}>
          <ul className="max-h-64 divide-y divide-gray-100 overflow-y-auto text-sm">
            {(assignable ?? []).map((u) => (
              <li key={u.user_id} className="flex items-center justify-between py-2">
                <span>{u.full_name} <span className="text-xs text-gray-400">({u.role})</span></span>
                <button onClick={() => assignMutation.mutate(u.user_id)} className="rounded bg-blue-600 px-2 py-1 text-xs text-white">
                  Assign
                </button>
              </li>
            ))}
          </ul>
        </Modal>
      )}

      {showRelease && (
        <Modal title={showRelease === "release" ? "Release transaction" : "Decline transaction"} onClose={() => setShowRelease(null)}>
          <textarea
            className="mb-3 w-full rounded border border-gray-300 p-2 text-sm"
            rows={3}
            placeholder="Reason"
            value={releaseReason}
            onChange={(e) => setReleaseReason(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowRelease(null)} className="rounded border px-3 py-1.5 text-sm">Cancel</button>
            <button onClick={() => releaseMutation.mutate()} disabled={!releaseReason} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
              Confirm
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
