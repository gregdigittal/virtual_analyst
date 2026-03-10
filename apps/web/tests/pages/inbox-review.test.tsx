import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import ReviewPage from "@/app/(app)/inbox/[id]/review/page";

// Add missing assignments methods
if (!mockApi.assignments.get) {
  (mockApi.assignments as Record<string, unknown>).get = vi.fn(async () => ({}));
}
if (!mockApi.assignments.submitReview) {
  (mockApi.assignments as Record<string, unknown>).submitReview = vi.fn(async () => ({}));
}

// Ensure get returns assignment data for rendering
mockApi.assignments.get = vi.fn(async () => ({
  assignment_id: "a-1",
  entity_type: "draft",
  entity_id: "draft-1",
  assignee_user_id: "other-user",
  status: "submitted",
  instructions: "Review this draft",
  created_at: "2026-01-01T00:00:00Z",
}));

function renderPage() {
  return render(
    <ToastProvider>
      <ReviewPage />
    </ToastProvider>,
  );
}

describe("ReviewPage", () => {
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
      expect(screen.getByText(/Review:/)).toBeInTheDocument();
    });
  });

  it("does not render content when not authenticated", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(/Review:/)).toBeNull();
  });
});
