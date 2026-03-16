/**
 * PIM backtest page smoke tests.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockGetAuthContext, mockApi } from "./setup";
import BacktestStudioPage from "@/app/(app)/pim/backtest/page";

beforeEach(() => {
  mockGetAuthContext.mockResolvedValue({
    accessToken: "test-token",
    tenantId: "tenant-test",
    userId: "user-test",
    tenantIdIsFallback: false,
  });
  mockApi.pim.backtest.summary.mockResolvedValue({ items: [] });
});

describe("Backtest Studio page", () => {
  it("renders page heading", async () => {
    render(<BacktestStudioPage />);
    await waitFor(() => {
      expect(screen.getByText(/Backtest Studio/i)).toBeTruthy();
    });
  });

  it("shows empty state when no strategies", async () => {
    mockApi.pim.backtest.summary.mockResolvedValue({ items: [] });
    render(<BacktestStudioPage />);
    await waitFor(() => {
      expect(screen.getByText(/No backtest strategies found/i)).toBeTruthy();
    });
  });

  it("renders strategy row when summary has data", async () => {
    mockApi.pim.backtest.summary.mockResolvedValue({
      items: [
        {
          strategy_label: "momentum-v1",
          run_count: 5,
          avg_cumulative_return: 0.32,
          avg_sharpe_ratio: 1.1,
          avg_ic_mean: 0.07,
          avg_icir: 1.4,
          best_cumulative_return: 0.55,
          worst_cumulative_return: 0.1,
        },
      ],
    });
    render(<BacktestStudioPage />);
    await waitFor(() => {
      expect(screen.getByText("momentum-v1")).toBeTruthy();
    });
  });

  it("does not call the API when auth is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    mockApi.pim.backtest.summary.mockClear();
    render(<BacktestStudioPage />);
    await waitFor(() => {
      expect(mockApi.pim.backtest.summary).not.toHaveBeenCalled();
    });
  });
});
