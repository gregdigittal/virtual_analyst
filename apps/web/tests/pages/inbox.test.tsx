import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import InboxPage from "@/app/(app)/inbox/page";

// Add missing assignments methods to mock API
if (!mockApi.assignments.listPool) {
  (mockApi.assignments as Record<string, unknown>).listPool = vi.fn(async () => ({
    assignments: [],
    total: 0,
  }));
}
if (!mockApi.assignments.claim) {
  (mockApi.assignments as Record<string, unknown>).claim = vi.fn(async () => ({}));
}
if (!mockApi.assignments.submit) {
  (mockApi.assignments as Record<string, unknown>).submit = vi.fn(async () => ({}));
}

function renderPage() {
  return render(
    <ToastProvider>
      <InboxPage />
    </ToastProvider>,
  );
}

describe("InboxPage", () => {
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
      expect(screen.getByRole("heading", { name: /Task Inbox/i })).toBeInTheDocument();
    });
  });
});
