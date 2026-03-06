import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import IntegrationsPage from "@/app/(app)/settings/integrations/page";

if (!(mockApi as Record<string, unknown>).integrations) {
  (mockApi as Record<string, unknown>).integrations = {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    initiate: vi.fn(async () => ({ redirect_url: "" })),
    sync: vi.fn(async () => ({})),
    snapshots: vi.fn(async () => ({ snapshots: [] })),
    disconnect: vi.fn(async () => ({})),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <IntegrationsPage />
    </ToastProvider>,
  );
}

describe("IntegrationsPage", () => {
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
      expect(screen.getByRole("heading", { name: /Integrations/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
