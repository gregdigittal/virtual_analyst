import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockApi, mockGetAuthContext } from "./setup";

import { ToastProvider } from "@/components/ui";
import DraftDetailPage from "@/app/drafts/[id]/page";

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

function renderPage() {
  return render(
    <ToastProvider>
      <DraftDetailPage />
    </ToastProvider>,
  );
}

describe("DraftDetailPage", () => {
  beforeEach(() => {
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
    mockApi.drafts.get.mockResolvedValue({
      draft_session_id: "draft-1",
      parent_baseline_id: "b-1",
      parent_baseline_version: null,
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      workspace: {
        assumptions: {
          funding: { debt_facilities: [], equity_raises: [], dividends: null },
          revenue_streams: [],
        },
        distributions: [],
        correlation_matrix: [],
        chat_history: [],
        pending_proposals: [],
      },
    });
  });

  it("renders structured editor tabs", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Funding")).toBeInTheDocument();
      expect(screen.getByText("Revenue")).toBeInTheDocument();
      expect(screen.getByText("Correlations")).toBeInTheDocument();
    });
  });
});
