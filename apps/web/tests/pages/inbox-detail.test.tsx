import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import AssignmentDetailPage from "@/app/(app)/inbox/[id]/page";

// Add missing assignments methods
if (!mockApi.assignments.get) {
  (mockApi.assignments as Record<string, unknown>).get = vi.fn(async () => ({
    assignment_id: "a-1",
    entity_type: "draft",
    entity_id: "draft-1",
    assignee_user_id: "user-test",
    status: "pending",
    instructions: "Review this draft",
    created_at: "2026-01-01T00:00:00Z",
  }));
}
if (!mockApi.assignments.submit) {
  (mockApi.assignments as Record<string, unknown>).submit = vi.fn(async () => ({}));
}
if (!mockApi.assignments.update) {
  (mockApi.assignments as Record<string, unknown>).update = vi.fn(async () => ({}));
}

// Ensure get returns assignment data for rendering
const originalGet = mockApi.assignments.get;
mockApi.assignments.get = vi.fn(async () => ({
  assignment_id: "a-1",
  workflow_instance_id: null,
  entity_type: "draft",
  entity_id: "draft-1",
  assignee_user_id: "user-test",
  assigned_by_user_id: null,
  status: "pending",
  deadline: null,
  instructions: "Review this draft",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: null,
}));

function renderPage() {
  return render(
    <ToastProvider>
      <AssignmentDetailPage />
    </ToastProvider>,
  );
}

describe("AssignmentDetailPage", () => {
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
      expect(screen.getByText(/draft — draft-1/)).toBeInTheDocument();
    });
  });

  it("does not render content when not authenticated", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(/draft — draft-1/)).toBeNull();
  });
});
