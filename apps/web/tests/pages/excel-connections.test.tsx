import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import ExcelConnectionsPage from "@/app/(app)/excel-connections/page";

// Add excelConnections namespace to mock API
if (!(mockApi as Record<string, unknown>).excelConnections) {
  (mockApi as Record<string, unknown>).excelConnections = {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    create: vi.fn(async () => ({ excel_connection_id: "ec-1" })),
    pull: vi.fn(async () => ({ values: [] })),
    push: vi.fn(async () => ({})),
    delete: vi.fn(async () => ({})),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <ExcelConnectionsPage />
    </ToastProvider>,
  );
}

describe("ExcelConnectionsPage", () => {
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
      expect(screen.getByRole("heading", { name: /Excel Connections/i })).toBeInTheDocument();
    });
  });
});
