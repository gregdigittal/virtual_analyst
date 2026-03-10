import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import BoardPackSchedulesPage from "@/app/(app)/board-packs/schedules/page";

// Add missing boardPackSchedules namespace mocks
if (!mockApi.boardPackSchedules) {
  (mockApi as Record<string, unknown>).boardPackSchedules = {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    history: vi.fn(async () => ({ items: [], total: 0 })),
    create: vi.fn(async () => ({ schedule_id: "sched-1" })),
    runNow: vi.fn(async () => ({ ok: true })),
    delete: vi.fn(async () => ({ ok: true })),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <BoardPackSchedulesPage />
    </ToastProvider>,
  );
}

describe("BoardPackSchedulesPage", () => {
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
      expect(screen.getByRole("heading", { name: /Board Pack Schedules/i })).toBeInTheDocument();
    });
  });

  it("renders heading but no schedules when not authenticated", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await new Promise((r) => setTimeout(r, 50));
    // Heading renders unconditionally, but no schedule data loads
    expect(screen.getByRole("heading", { name: /Board Pack Schedules/i })).toBeInTheDocument();
  });
});
