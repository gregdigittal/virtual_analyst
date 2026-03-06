import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import BoardPackBuilderPage from "@/app/(app)/board-packs/[id]/builder/page";

// Add boardPacks.get and boardPacks.update to mock API
if (!mockApi.boardPacks.get) {
  (mockApi.boardPacks as Record<string, unknown>).get = vi.fn(async () => ({
    board_pack_id: "bp-1",
    label: "Q1 Board Pack",
    run_id: "run-1",
    status: "draft",
    section_order: [],
    narrative_json: null,
    error_message: null,
  }));
}
if (!mockApi.boardPacks.update) {
  (mockApi.boardPacks as Record<string, unknown>).update = vi.fn(async () => ({}));
}

function renderPage() {
  return render(
    <ToastProvider>
      <BoardPackBuilderPage />
    </ToastProvider>,
  );
}

describe("BoardPackBuilderPage", () => {
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
      expect(screen.getByRole("heading", { name: /Report Builder/i })).toBeInTheDocument();
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
