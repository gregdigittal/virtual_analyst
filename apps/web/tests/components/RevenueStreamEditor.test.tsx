import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RevenueStreamEditor } from "@/components/RevenueStreamEditor";

const sampleStreams = [
  {
    label: "SaaS Revenue",
    stream_type: "recurring",
    business_line: "Cloud",
    market: "US",
    launch_month: 3,
    ramp_up_months: 6,
    ramp_curve: "s_curve",
  },
];

describe("RevenueStreamEditor", () => {
  it("renders existing stream fields", () => {
    render(<RevenueStreamEditor streams={sampleStreams} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("SaaS Revenue")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Cloud")).toBeInTheDocument();
    expect(screen.getByDisplayValue("US")).toBeInTheDocument();
  });

  it("shows ramp fields when launch_month is set", () => {
    render(<RevenueStreamEditor streams={sampleStreams} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("6")).toBeInTheDocument();
    expect(screen.getByDisplayValue("s_curve")).toBeInTheDocument();
  });

  it("hides ramp_up_months when launch_month is empty", () => {
    const noLaunch = [{ ...sampleStreams[0], launch_month: null, ramp_up_months: null, ramp_curve: null }];
    render(<RevenueStreamEditor streams={noLaunch} onChange={vi.fn()} />);
    expect(screen.queryByDisplayValue("6")).not.toBeInTheDocument();
  });

  it("adds a new empty stream row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RevenueStreamEditor streams={[]} onChange={onChange} />);
    await user.click(screen.getByText(/Add Stream/i));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toHaveLength(1);
  });

  it("deletes a stream row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RevenueStreamEditor streams={sampleStreams} onChange={onChange} />);
    await user.click(screen.getByTitle(/delete/i));
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][0]).toHaveLength(0);
  });

  it("updates business_line on change", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RevenueStreamEditor streams={sampleStreams} onChange={onChange} />);
    const blInput = screen.getByDisplayValue("Cloud");
    await user.clear(blInput);
    await user.type(blInput, "Enterprise");
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall[0].business_line).toBe("Enterprise");
  });
});
