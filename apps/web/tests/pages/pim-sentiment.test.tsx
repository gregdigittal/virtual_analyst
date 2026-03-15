import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import type { PimSentimentDashboardResponse } from "@/lib/api";

import { ToastProvider } from "@/components/ui";
import PimSentimentPage from "@/app/(app)/pim/sentiment/page";

function renderPage() {
  return render(
    <ToastProvider>
      <PimSentimentPage />
    </ToastProvider>,
  );
}

describe("PimSentimentPage", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockGetAuthContext.mockClear();
    mockApi.pim.sentiment.dashboard.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
    mockApi.pim.sentiment.dashboard.mockResolvedValue({ items: [], total: 0 });
  });

  it("renders the Sentiment Monitor heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Sentiment Monitor/i })).toBeInTheDocument();
    });
  });

  it("shows empty state when no companies exist", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/No companies in your universe yet/i),
      ).toBeInTheDocument();
    });
  });

  it("renders dashboard rows when items are returned", async () => {
    const mockDashboardResponse: PimSentimentDashboardResponse = {
      items: [
        {
          company_id: "co-1",
          company_name: "Acme Corp",
          ticker: "ACME",
          sector: "Finance",
          latest_avg_sentiment: 0.45,
          latest_avg_confidence: 0.8,
          trend_direction: "up",
          total_signals: 12,
          latest_signal_count: 3,
          source_breakdown: { news: 3 },
          latest_period_start: "2026-03-01",
          latest_period_end: "2026-03-07",
          latest_signal: {
            headline: "Acme beats Q1 expectations",
            sentiment_score: 0.5,
            source_type: "news",
            published_at: "2026-03-01T00:00:00Z",
            confidence: 0.85,
          },
        },
      ],
      total: 1,
    };
    mockApi.pim.sentiment.dashboard.mockResolvedValue(mockDashboardResponse);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
      expect(screen.getByText("ACME")).toBeInTheDocument();
    });
  });

  it("does not call the API when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    // Page stays in loading state when auth is absent (no redirect — useEffect returns early)
    await waitFor(() => {
      expect(mockApi.pim.sentiment.dashboard).not.toHaveBeenCalled();
    });
  });

  it("shows error state when dashboard fetch fails", async () => {
    mockApi.pim.sentiment.dashboard.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });
});
