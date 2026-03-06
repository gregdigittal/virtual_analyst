import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import WorkflowDetailPage from "@/app/(app)/workflows/[id]/page";

// Add workflows.getInstance and workflows.getTemplate to mock API
if (!mockApi.workflows.getInstance) {
  (mockApi.workflows as Record<string, unknown>).getInstance = vi.fn(async () => ({
    instance_id: "wf-inst-1",
    template_id: "wf-tpl-1",
    entity_type: "baseline",
    entity_id: "b-1",
    status: "active",
    current_stage_index: 0,
    created_at: "2026-01-01T00:00:00Z",
  }));
}
if (!mockApi.workflows.getTemplate) {
  (mockApi.workflows as Record<string, unknown>).getTemplate = vi.fn(async () => ({
    template_id: "wf-tpl-1",
    name: "Approval Flow",
    stages: [
      { name: "Draft Review", assignee_rule: "creator" },
      { name: "Manager Approval", assignee_rule: "manager" },
    ],
  }));
}

function renderPage() {
  return render(
    <ToastProvider>
      <WorkflowDetailPage />
    </ToastProvider>,
  );
}

describe("WorkflowDetailPage", () => {
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
      expect(screen.getByRole("heading", { name: /Workflow/i })).toBeInTheDocument();
    });
  });

  it("redirects to /login when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });
});
