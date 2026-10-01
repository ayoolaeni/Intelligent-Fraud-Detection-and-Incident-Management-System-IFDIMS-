import { describe, expect, it } from "vitest";
import { formatMoney, formatDateTime } from "../components/format";

describe("formatMoney", () => {
  it("formats a numeric string with the naira sign and 2 decimals", () => {
    expect(formatMoney("1250000")).toBe("₦1,250,000.00");
  });

  it("formats a plain number", () => {
    expect(formatMoney(1000)).toBe("₦1,000.00");
  });

  it("handles invalid input gracefully", () => {
    expect(formatMoney("not-a-number")).toBe("₦0.00");
  });
});

describe("formatDateTime", () => {
  it("renders a readable date/time string", () => {
    const result = formatDateTime("2026-01-15T21:42:10+01:00");
    expect(result).toMatch(/2026/);
  });
});
