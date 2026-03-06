import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import RunValuationPage from "@/app/(app)/runs/[id]/valuation/page";

// Add runs.getValuation to mock API
if (!mockApi.runs.getValuation) {
  (mockApi.runs as Record<string, unknown>).getValuation = vi.fn(async () => ({
    dcf: {
      enterprise_value: 1000000,
      pv_explicit: 600000,
      pv_terminal: 400000,
      wacc: 0.1,
    },
    multiples: {
      implied_ev_range: [800000, 1200000],
    },
  }));
}

function renderPage() {
  return render(
    <ToastProvider>
      <RunValuationPage />
    </ToastProvider>,
  );
}

describe("RunValuationPage", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
  });

  it("renders without crashing", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Valuation/i })).toBeInTheDocument();
    });
  });

  it("redirects to /login when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });
});
