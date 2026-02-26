import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockApi, mockGetAuthContext } from "./setup";

import { ToastProvider } from "@/components/ui";
import RunDetailPage from "@/app/(app)/runs/[id]/page";

function renderPage() {
  return render(
    <ToastProvider>
      <RunDetailPage />
    </ToastProvider>,
  );
}

describe("RunDetailPage - Revenue Segment Chart", () => {
  beforeEach(() => {
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockApi.runs.get.mockResolvedValue({
      run_id: "run-1",
      baseline_id: "b-1",
      status: "completed",
      created_at: "2026-01-01T00:00:00Z",
      statements: null,
      kpis: [],
      mc_summary: null,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockApi.runs.getStatements.mockResolvedValue({
      income_statement: [{ label: "Revenue", P0: 100, P1: 200 }],
      balance_sheet: [],
      cash_flow: [],
      periods: ["P0", "P1"],
      revenue_by_segment: {
        saas: [80, 150],
        services: [20, 50],
      },
    } as any);
    mockApi.runs.getKpis.mockResolvedValue([]);
  });

  it("renders the revenue by segment section with chart", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Revenue by Segment/i)).toBeInTheDocument();
    });
    // Recharts renders SVG — segment names should appear in legend
    await waitFor(() => {
      expect(screen.getByText("saas")).toBeInTheDocument();
      expect(screen.getByText("services")).toBeInTheDocument();
    });
  });
});
