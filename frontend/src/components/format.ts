export function formatMoney(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(n)) return "₦0.00";
  return `₦${n.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-NG", {
      timeZone: "Africa/Lagos",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatCountdown(iso: string): string {
  const due = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = due - now;
  const sign = diffMs < 0 ? "-" : "";
  const abs = Math.abs(diffMs);
  const hours = Math.floor(abs / 3_600_000);
  const minutes = Math.floor((abs % 3_600_000) / 60_000);
  if (hours > 0) return `${sign}${hours}h ${minutes}m`;
  return `${sign}${minutes}m`;
}
