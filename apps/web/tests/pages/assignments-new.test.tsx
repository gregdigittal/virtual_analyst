import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import NewAssignmentPage from "@/app/(app)/assignments/new/page";

// Add missing assignments.create mock
if (!mockApi.assignments.create) {
  (mockApi.assignments as Record<string, unknown>).create = vi.fn(async () => ({
    assignment_id: "a-1",
  }));
}

function renderPage() {
  return render(
    <ToastProvider>
      <NewAssignmentPage />
    </ToastProvider>,
  );
}

describe("NewAssignmentPage", () => {
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
      expect(screen.getByRole("heading", { name: /New assignment/i })).toBeInTheDocument();
    });
  });

  it("does not render form when not authenticated", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    // Wait for auth check to resolve, then verify heading is not rendered
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("heading", { name: /New assignment/i })).toBeNull();
  });
});
