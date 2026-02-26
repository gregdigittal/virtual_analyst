import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConsolidatedResults } from "@/components/ConsolidatedResults";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => {
    return <a href={href} {...props}>{children}</a>;
  },
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
}));

const sampleResult = {
  consolidated_is: { income_statement: [{ label: "Revenue", P0: 100000 }] },
  consolidated_bs: { balance_sheet: [] },
  consolidated_cf: { cash_flow: [] },
  entity_results: [
    { entity_id: "entity-a", currency: "USD", ownership_pct: 100 },
    { entity_id: "entity-b", currency: "EUR", ownership_pct: 60 },
  ],
  minority_interest: {
    nci_profit: [5000, 6000, 7000],
    nci_equity: [20000, 26000, 33000],
  },
  eliminations: [
    { from_entity_id: "entity-a", to_entity_id: "entity-b", link_type: "revenue", amount_per_period: [10000, 12000] },
    { from_entity_id: "entity-a", to_entity_id: "entity-b", link_type: "loan", amount_per_period: [50000, 50000] },
  ],
  fx_rates_used: { "EUR/USD": 1.08 },
  integrity: { warnings: ["FX mismatch on entity-b"], errors: [] },
};

const entityRunMap = { "entity-a": "run-a", "entity-b": "run-b" };

describe("ConsolidatedResults", () => {
  it("renders entity breakdown with clickable rows when entityRunMap provided", async () => {
    const user = userEvent.setup();
    render(<ConsolidatedResults result={sampleResult} entityRunMap={entityRunMap} />);
    await user.click(screen.getByText("Entity Breakdown"));
    const link = screen.getByRole("link", { name: /entity-a/i });
    expect(link).toHaveAttribute("href", "/runs/run-a");
  });

  it("renders NCI section with profit data", async () => {
    const user = userEvent.setup();
    render(<ConsolidatedResults result={sampleResult} />);
    await user.click(screen.getByText("NCI"));
    expect(screen.getByText(/NCI Share of Profit/i)).toBeInTheDocument();
  });

  it("renders IC elimination summary totals", async () => {
    const user = userEvent.setup();
    render(<ConsolidatedResults result={sampleResult} />);
    await user.click(screen.getByText("IC Eliminations"));
    // The summary footer row shows "Total" label and the computed grand total (122,000)
    const totalElements = screen.getAllByText(/Total/i);
    expect(totalElements.length).toBeGreaterThanOrEqual(2); // header "Total Eliminated" + footer "Total"
    // Grand total: (10000+12000) + (50000+50000) = 122,000
    expect(screen.getByText("122,000")).toBeInTheDocument();
  });

  it("renders integrity warnings", async () => {
    const user = userEvent.setup();
    render(<ConsolidatedResults result={sampleResult} />);
    await user.click(screen.getByText("FX & Integrity"));
    expect(screen.getByText(/FX mismatch/i)).toBeInTheDocument();
  });
});
