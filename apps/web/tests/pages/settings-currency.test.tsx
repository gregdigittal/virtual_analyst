import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import CurrencyPage from "@/app/(app)/settings/currency/page";

if (!(mockApi as Record<string, unknown>).currency) {
  (mockApi as Record<string, unknown>).currency = {
    getSettings: vi.fn(async () => ({ base_currency: "USD", display_decimals: 2 })),
    listRates: vi.fn(async () => ({ items: [], total: 0 })),
    updateSettings: vi.fn(async () => ({})),
    addRate: vi.fn(async () => ({ rate_id: "r-1" })),
    deleteRate: vi.fn(async () => ({})),
    convert: vi.fn(async () => ({ result: 0 })),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <CurrencyPage />
    </ToastProvider>,
  );
}

describe("CurrencyPage", () => {
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
      expect(screen.getByRole("heading", { name: /Currency Settings/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
