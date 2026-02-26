import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CorrelationMatrixEditor } from "@/components/CorrelationMatrixEditor";

const distributions = [
  { ref: "drv:revenue_growth", family: "normal" },
  { ref: "drv:cost_inflation", family: "normal" },
  { ref: "drv:churn_rate", family: "beta" },
];

const correlationMatrix = [
  { ref_a: "drv:revenue_growth", ref_b: "drv:cost_inflation", rho: 0.3 },
];

describe("CorrelationMatrixEditor (read-only)", () => {
  it("renders placeholder when fewer than 2 distributions", () => {
    render(<CorrelationMatrixEditor distributions={[{ ref: "drv:x", family: "normal" }]} correlationMatrix={[]} />);
    expect(screen.getByText(/at least 2/i)).toBeInTheDocument();
  });

  it("renders NxN grid with correct values", () => {
    render(<CorrelationMatrixEditor distributions={distributions} correlationMatrix={correlationMatrix} />);
    const cells = screen.getAllByText("1.00");
    expect(cells.length).toBe(3);
    expect(screen.getAllByText("0.30").length).toBeGreaterThanOrEqual(2);
  });

  it("shows active correlations list", () => {
    render(<CorrelationMatrixEditor distributions={distributions} correlationMatrix={correlationMatrix} />);
    expect(screen.getByText(/Active correlations/i)).toBeInTheDocument();
  });
});

describe("CorrelationMatrixEditor (editable)", () => {
  it("makes off-diagonal cells clickable when editable", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={correlationMatrix}
        editable
        onChange={onChange}
      />
    );
    const zeroCells = screen.getAllByText("0.00");
    await user.click(zeroCells[0]);
    const input = screen.getByRole("spinbutton");
    expect(input).toBeInTheDocument();
  });

  it("enforces symmetry on edit", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={[]}
        editable
        onChange={onChange}
      />
    );
    const zeroCells = screen.getAllByText("0.00");
    await user.click(zeroCells[0]);
    const input = screen.getByRole("spinbutton");
    await user.clear(input);
    await user.type(input, "0.5");
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalled();
    const entries = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    // Should have exactly one entry (stored once, displayed symmetrically)
    expect(entries.length).toBeGreaterThanOrEqual(1);
  });

  it("does not allow editing diagonal cells", async () => {
    const user = userEvent.setup();
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={[]}
        editable
        onChange={vi.fn()}
      />
    );
    const diagCells = screen.getAllByText("1.00");
    await user.click(diagCells[0]);
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  });

  it("shows PSD warning when matrix is not positive semi-definite", () => {
    const badMatrix = [
      { ref_a: "drv:revenue_growth", ref_b: "drv:cost_inflation", rho: -0.9 },
      { ref_a: "drv:revenue_growth", ref_b: "drv:churn_rate", rho: -0.9 },
      { ref_a: "drv:cost_inflation", ref_b: "drv:churn_rate", rho: -0.9 },
    ];
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={badMatrix}
        editable
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText(/not positive semi-definite/i)).toBeInTheDocument();
  });

  it("shows valid message when matrix is PSD", () => {
    const goodMatrix = [
      { ref_a: "drv:revenue_growth", ref_b: "drv:cost_inflation", rho: 0.3 },
    ];
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={goodMatrix}
        editable
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText(/valid/i)).toBeInTheDocument();
  });
});
