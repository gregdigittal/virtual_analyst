import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import BillingPage from "@/app/(app)/settings/billing/page";

if (!(mockApi as Record<string, unknown>).billing) {
  (mockApi as Record<string, unknown>).billing = {
    listPlans: vi.fn(async () => ({ plans: [] })),
    getSubscription: vi.fn(async () => null),
    getUsage: vi.fn(async () => ({ usage: [] })),
    createOrUpdateSubscription: vi.fn(async () => ({})),
    cancelSubscription: vi.fn(async () => ({})),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <BillingPage />
    </ToastProvider>,
  );
}

describe("BillingPage", () => {
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
      expect(screen.getByRole("heading", { name: /Billing/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    // Settings pages silently return on null auth instead of redirecting
    expect(container).toBeTruthy();
  });
});
