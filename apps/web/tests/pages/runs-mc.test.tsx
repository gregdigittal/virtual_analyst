import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import RunMcPage from "@/app/(app)/runs/[id]/mc/page";

// Add runs.getMc to mock API
if (!mockApi.runs.getMc) {
  (mockApi.runs as Record<string, unknown>).getMc = vi.fn(async () => ({
    num_simulations: 1000,
    seed: 42,
    percentiles: {
      revenue: { p5: [100], p10: [110], p25: [120], p50: [130], p75: [140], p90: [150], p95: [160] },
      ebitda: { p5: [50], p10: [55], p25: [60], p50: [65], p75: [70], p90: [75], p95: [80] },
      net_income: { p5: [30], p10: [33], p25: [36], p50: [40], p75: [44], p90: [48], p95: [52] },
      fcf: { p5: [20], p10: [22], p25: [25], p50: [28], p75: [31], p90: [34], p95: [37] },
    },
    summary: {},
  }));
}

function renderPage() {
  return render(
    <ToastProvider>
      <RunMcPage />
    </ToastProvider>,
  );
}

describe("RunMcPage", () => {
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
      expect(screen.getByRole("heading", { name: /Monte Carlo Results/i })).toBeInTheDocument();
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
