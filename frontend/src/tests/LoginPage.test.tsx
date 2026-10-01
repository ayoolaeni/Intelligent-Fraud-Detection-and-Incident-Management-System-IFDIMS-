import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "../pages/LoginPage";
import { AuthProvider } from "../auth/AuthContext";
import * as api from "../api/endpoints";

vi.mock("../api/endpoints");

beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("LoginPage", () => {
  it("renders email and password fields", () => {
    renderLogin();
    expect(screen.getByText("IFDIMS")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows a server error message on failed login", async () => {
    vi.mocked(api.login).mockRejectedValueOnce({
      response: { data: { detail: "Invalid email or password", code: "INVALID_CREDENTIALS" } },
    });
    renderLogin();

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "bad@test.local" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid email or password")).toBeInTheDocument();
    });
  });
});
