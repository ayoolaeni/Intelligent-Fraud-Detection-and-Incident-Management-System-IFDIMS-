import React, { useState } from "react";
import { downloadAuthenticated } from "../api/download";
import { reportUrl } from "../api/endpoints";
import { errorMessage } from "../api/client";
import { Card, ErrorBanner } from "../components/Common";

const REPORT_TYPES = [
  { key: "cases", label: "Case list", formats: ["csv"] },
  { key: "alerts", label: "Alerts", formats: ["csv"] },
  { key: "fraud-summary", label: "Fraud summary", formats: ["csv", "pdf"] },
  { key: "nibss-incidents", label: "NIBSS incident export", formats: ["csv"] },
] as const;

export function ReportsPage() {
  const [kind, setKind] = useState<(typeof REPORT_TYPES)[number]["key"]>("fraud-summary");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [channel, setChannel] = useState("");
  const [format, setFormat] = useState("csv");
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const current = REPORT_TYPES.find((r) => r.key === kind)!;

  const handleDownload = async () => {
    setError(null);
    setDownloading(true);
    try {
      const params: Record<string, any> = { format };
      if (from) params.from = new Date(from).toISOString();
      if (to) params.to = new Date(to).toISOString();
      if (channel) params.channel = channel;
      await downloadAuthenticated(reportUrl(kind, params), `${kind}.${format}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Reports</h1>
      {error && <ErrorBanner message={error} />}
      <Card>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Report type</label>
            <select
              value={kind}
              onChange={(e) => {
                const k = e.target.value as typeof kind;
                setKind(k);
                setFormat(REPORT_TYPES.find((r) => r.key === k)!.formats[0]);
              }}
              className="w-full rounded border-gray-300 text-sm"
            >
              {REPORT_TYPES.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">From</label>
              <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">To</label>
              <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-full rounded border-gray-300 text-sm" />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Channel</label>
            <select value={channel} onChange={(e) => setChannel(e.target.value)} className="w-full rounded border-gray-300 text-sm">
              <option value="">All channels</option>
              {["NIP", "MOBILE", "USSD", "INTERNET", "POS", "ATM"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          {current.formats.length > 1 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Format</label>
              <select value={format} onChange={(e) => setFormat(e.target.value)} className="w-full rounded border-gray-300 text-sm">
                {current.formats.map((f) => (
                  <option key={f} value={f}>{f.toUpperCase()}</option>
                ))}
              </select>
            </div>
          )}
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {downloading ? "Preparing..." : "Download"}
          </button>
        </div>
      </Card>
    </div>
  );
}
