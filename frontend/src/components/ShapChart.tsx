import React from "react";
import type { TopFactor } from "../api/types";

/** Horizontal bar chart of the top SHAP factors: red bars increase risk,
 * blue bars decrease it, each with its plain-English description beside it
 * (Section 12.1 alert detail page). */
export function ShapChart({ factors }: { factors: TopFactor[] }) {
  if (!factors.length) {
    return <p className="text-sm text-gray-500">No explanation factors available.</p>;
  }
  const maxAbs = Math.max(...factors.map((f) => Math.abs(f.contribution)), 0.0001);

  return (
    <div className="space-y-3" data-testid="shap-chart">
      {factors.map((f) => {
        const widthPct = Math.max((Math.abs(f.contribution) / maxAbs) * 100, 4);
        const increases = f.contribution > 0;
        return (
          <div key={f.feature} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-gray-800">{f.label}</span>
              <span className={increases ? "text-red-600" : "text-blue-600"}>
                {increases ? "+" : ""}
                {f.contribution.toFixed(3)}
              </span>
            </div>
            <div className="h-2 w-full rounded bg-gray-100">
              <div
                className={`h-2 rounded ${increases ? "bg-red-500" : "bg-blue-500"}`}
                style={{ width: `${widthPct}%` }}
              />
            </div>
            <p className="text-xs text-gray-500">{f.description}</p>
          </div>
        );
      })}
    </div>
  );
}
