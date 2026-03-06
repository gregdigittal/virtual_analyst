import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import AuditPage from "@/app/(app)/settings/audit/page";

if (!(mockApi as Record<string, unknown>).audit) {
  (mockApi as Record<string, unknown>).audit = {
    catalog: vi.fn(async () => ({ event_types: [] })),
    list: vi.fn(async () => ({ items: [], total: 0 })),
    exportUrl: vi.fn(() => "http://localhost:8000/api/v1/audit/export"),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <AuditPage />
    </ToastProvider>,
  );
}

describe("AuditPage", () => {
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
      expect(screen.getByRole("heading", { name: /Audit Log/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
