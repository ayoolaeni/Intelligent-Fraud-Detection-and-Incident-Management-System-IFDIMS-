import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "../components/Layout";
import { AuthContext } from "../auth/AuthContext";
import * as api from "../api/endpoints";
import type { User } from "../api/types";

vi.mock("../api/endpoints");

function renderLayoutAs(user: User) {
  vi.mocked(api.listNotifications).mockResolvedValue([]);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const authValue = {
    user,
    loading: false,
    sessionExpired: false,
    login: vi.fn(),
    logout: vi.fn(),
    clearSessionExpired: vi.fn(),
  };
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={authValue as any}>
          <Layout />
        </AuthContext.Provider>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("Layout role-based menu", () => {
  it("hides admin-only links for an analyst", () => {
    renderLayoutAs({ user_id: "1", full_name: "A Analyst", email: "a@test.local", role: "analyst" });
    expect(screen.getByText("Alerts")).toBeInTheDocument();
    expect(screen.getByText("Cases")).toBeInTheDocument();
    expect(screen.queryByText("Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
  });

  it("shows admin links for an admin", () => {
    renderLayoutAs({ user_id: "2", full_name: "Admin User", email: "adm@test.local", role: "admin" });
    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Models")).toBeInTheDocument();
    expect(screen.queryByText("Alerts")).not.toBeInTheDocument();
  });
});
