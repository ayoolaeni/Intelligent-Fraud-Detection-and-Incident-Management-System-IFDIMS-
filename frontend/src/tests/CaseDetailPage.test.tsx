import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CaseDetailPage } from "../pages/CaseDetailPage";
import { AuthContext } from "../auth/AuthContext";
import * as api from "../api/endpoints";
import type { CaseDetail, User } from "../api/types";

vi.mock("../api/endpoints");

const baseCase: CaseDetail = {
  case: {
    case_id: "c1",
    case_number: "FC-2026-000001",
    title: "Test case",
    source: "ALERT",
    priority: "high",
    status: "ASSIGNED",
    outcome: null,
    assigned_to: "u1",
    assigned_to_name: "Analyst One",
    amount_at_risk: "100000.00",
    amount_recovered: "0.00",
    opened_at: "2026-01-01T10:00:00Z",
    ack_due_at: "2026-01-01T10:30:00Z",
    resolve_due_at: "2026-01-02T10:00:00Z",
    closed_at: null,
    sla_state: "ok",
  },
  description: "A test case",
  alert_id: null,
  txn_id: null,
  account_number_masked: "******1234",
  fraud_type: null,
  notes: [],
  attachments: [],
  allowed_transitions: ["UNDER_INVESTIGATION"],
  can_assign: false,
  can_release_decline: false,
};

beforeEach(() => {
  vi.mocked(api.listAssignableUsers).mockResolvedValue([]);
  vi.mocked(api.getCaseHistory).mockResolvedValue([]);
});

function renderAs(user: User, caseDetail: CaseDetail) {
  vi.mocked(api.getCase).mockResolvedValue(caseDetail);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const authValue = { user, loading: false, sessionExpired: false, login: vi.fn(), logout: vi.fn(), clearSessionExpired: vi.fn() };
  return render(
    <MemoryRouter initialEntries={["/cases/c1"]}>
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={authValue as any}>
          <Routes>
            <Route path="/cases/:id" element={<CaseDetailPage />} />
          </Routes>
        </AuthContext.Provider>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("CaseDetailPage action buttons", () => {
  it("renders a button for each allowed transition", async () => {
    renderAs({ user_id: "u1", full_name: "Analyst One", email: "a@test.local", role: "analyst" }, baseCase);
    expect(await screen.findByText("FC-2026-000001", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /UNDER INVESTIGATION/i })).toBeInTheDocument();
  });

  it("does not render the assign button when can_assign is false", async () => {
    renderAs({ user_id: "u1", full_name: "Analyst One", email: "a@test.local", role: "analyst" }, baseCase);
    await screen.findByText("FC-2026-000001", { exact: false });
    expect(screen.queryByRole("button", { name: /assign/i })).not.toBeInTheDocument();
  });

  it("renders the assign button for a supervisor when can_assign is true", async () => {
    renderAs(
      { user_id: "u2", full_name: "Supervisor One", email: "s@test.local", role: "supervisor" },
      { ...baseCase, can_assign: true }
    );
    expect(await screen.findByRole("button", { name: /reassign|assign/i })).toBeInTheDocument();
  });
});
