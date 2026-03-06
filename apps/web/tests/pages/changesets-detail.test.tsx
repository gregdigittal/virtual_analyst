import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import ChangesetDetailPage from "@/app/(app)/changesets/[id]/page";

// Add missing changesets namespace to mock API
(mockApi as Record<string, unknown>).changesets = {
  get: vi.fn(async () => ({
    changeset_id: "cs-1",
    baseline_id: "b-1",
    base_version: "v1",
    status: "draft",
    label: "Test changeset",
    created_at: "2026-01-01T00:00:00Z",
    overrides: [],
  })),
  test: vi.fn(async () => ({
    time_series: {},
    applied_overrides: 0,
  })),
  merge: vi.fn(async () => ({ new_version: "v2" })),
};

function renderPage() {
  return render(
    <ToastProvider>
      <ChangesetDetailPage />
    </ToastProvider>,
  );
}

describe("ChangesetDetailPage", () => {
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
      expect(screen.getByRole("heading", { name: /Changeset/i })).toBeInTheDocument();
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
