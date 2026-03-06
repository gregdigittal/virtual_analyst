import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import SensitivityPage from "@/app/(app)/runs/[id]/sensitivity/page";

// Add runs.getSensitivity and runs.postSensitivityHeatmap to mock API
if (!mockApi.runs.getSensitivity) {
  (mockApi.runs as Record<string, unknown>).getSensitivity = vi.fn(async () => ({
    base_fcf: 100000,
    pct: 0.1,
    drivers: [],
  }));
}
if (!mockApi.runs.postSensitivityHeatmap) {
  (mockApi.runs as Record<string, unknown>).postSensitivityHeatmap = vi.fn(async () => ({
    param_a: "tax_rate",
    param_b: "initial_cash",
    values_a: [0.1, 0.2],
    values_b: [50000, 100000],
    matrix: [[100, 200], [150, 250]],
    metric: "net_income",
  }));
}

function renderPage() {
  return render(
    <ToastProvider>
      <SensitivityPage />
    </ToastProvider>,
  );
}

describe("SensitivityPage", () => {
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
      expect(screen.getByRole("heading", { name: /Sensitivity Analysis/i })).toBeInTheDocument();
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
