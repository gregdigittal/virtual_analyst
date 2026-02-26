import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FundingEditor } from "@/components/FundingEditor";

const emptyFunding = { debt_facilities: [], equity_raises: [], dividends: null };

const sampleFunding = {
  debt_facilities: [
    {
      facility_id: "f-1",
      label: "Term Loan A",
      type: "term_loan",
      limit: 500000,
      interest_rate: 0.05,
      draw_schedule: [{ month: 0, amount: 250000 }],
      repayment_schedule: [{ month: 6, amount: 125000 }],
      is_cash_plug: false,
    },
  ],
  equity_raises: [{ label: "Series A", amount: 1000000, month: 3 }],
  dividends: { policy: "fixed_amount", value: 50000 },
};

describe("FundingEditor", () => {
  it("renders empty state with add buttons", () => {
    const onChange = vi.fn();
    render(<FundingEditor funding={emptyFunding} onChange={onChange} />);
    expect(screen.getByText(/Add Facility/i)).toBeInTheDocument();
    expect(screen.getByText(/Add Raise/i)).toBeInTheDocument();
  });

  it("renders existing debt facility rows", () => {
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("Term Loan A")).toBeInTheDocument();
    expect(screen.getByDisplayValue("500000")).toBeInTheDocument();
  });

  it("calls onChange when adding a new debt facility", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={emptyFunding} onChange={onChange} />);
    await user.click(screen.getByText(/Add Facility/i));
    expect(onChange).toHaveBeenCalledTimes(1);
    const call = onChange.mock.calls[0][0];
    expect(call.debt_facilities).toHaveLength(1);
  });

  it("calls onChange when adding an equity raise", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={emptyFunding} onChange={onChange} />);
    await user.click(screen.getByText(/Add Raise/i));
    expect(onChange).toHaveBeenCalledTimes(1);
    const call = onChange.mock.calls[0][0];
    expect(call.equity_raises).toHaveLength(1);
  });

  it("renders dividend policy radio group", () => {
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/None/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Fixed Amount/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Payout Ratio/i)).toBeInTheDocument();
  });

  it("shows value input when Fixed Amount is selected", () => {
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    const valueInput = screen.getByDisplayValue("50000");
    expect(valueInput).toBeInTheDocument();
  });

  it("hides value input when None is selected", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={sampleFunding} onChange={onChange} />);
    await user.click(screen.getByLabelText(/^None$/));
    const call = onChange.mock.calls[0][0];
    expect(call.dividends.policy).toBe("none");
  });

  it("validates interest rate is between 0 and 1", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={sampleFunding} onChange={onChange} />);
    const rateInput = screen.getByDisplayValue("0.05");
    await user.clear(rateInput);
    await user.type(rateInput, "1.5");
    await user.tab();
    expect(screen.getByText(/0 and 1/i)).toBeInTheDocument();
  });

  it("expands draw schedule when chevron is clicked", async () => {
    const user = userEvent.setup();
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    const expandBtn = screen.getByTitle(/expand/i);
    await user.click(expandBtn);
    expect(screen.getByText(/Draw Schedule/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("250000")).toBeInTheDocument();
  });
});
