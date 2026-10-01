import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ShapChart } from "../components/ShapChart";

describe("ShapChart", () => {
  it("renders a bar and description for each factor", () => {
    render(
      <ShapChart
        factors={[
          { feature: "is_new_beneficiary", label: "New beneficiary", raw_value: 1, contribution: 0.41, description: "Beneficiary has never been paid before" },
          { feature: "account_age_days", label: "Account age", raw_value: 900, contribution: -0.12, description: "Account is 900 days old" },
        ]}
      />
    );

    expect(screen.getByText("New beneficiary")).toBeInTheDocument();
    expect(screen.getByText("Beneficiary has never been paid before")).toBeInTheDocument();
    expect(screen.getByText("Account age")).toBeInTheDocument();
    expect(screen.getByText("+0.410")).toBeInTheDocument();
    expect(screen.getByText("-0.120")).toBeInTheDocument();
  });

  it("renders a fallback message with no factors", () => {
    render(<ShapChart factors={[]} />);
    expect(screen.getByText(/No explanation factors/)).toBeInTheDocument();
  });
});
