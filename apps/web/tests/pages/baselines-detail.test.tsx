import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { mockReplace, mockPush, mockGetAuthContext, mockApi } from "./setup";

import { ToastProvider } from "@/components/ui";
import BaselineDetailPage from "@/app/baselines/[id]/page";

function renderPage() {
  return render(
    <ToastProvider>
      <BaselineDetailPage />
    </ToastProvider>,
  );
}

describe("BaselineDetailPage", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockPush.mockClear();
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
      expect(screen.getByRole("heading", { name: /Baseline/i })).toBeInTheDocument();
    });
  });

  it("redirects to /login when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("renders Edit Configuration button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Edit Configuration/i })).toBeInTheDocument();
    });
  });

  it("navigates to existing active draft when Edit Configuration is clicked", async () => {
    mockApi.drafts.list.mockResolvedValue({
      items: [{ draft_session_id: "draft-existing", status: "active" }],
      total: 1,
      limit: 50,
      offset: 0,
    });
    renderPage();
    const btn = await waitFor(() => screen.getByRole("button", { name: /Edit Configuration/i }));
    await act(async () => {
      fireEvent.click(btn);
    });
    expect(mockPush).toHaveBeenCalledWith("/drafts/draft-existing?tab=funding");
  });

  it("creates a new draft when no active draft exists", async () => {
    mockApi.drafts.list.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    mockApi.drafts.create.mockResolvedValue({ draft_session_id: "draft-new", status: "active", storage_path: "/tmp" });
    renderPage();
    const btn = await waitFor(() => screen.getByRole("button", { name: /Edit Configuration/i }));
    await act(async () => {
      fireEvent.click(btn);
    });
    expect(mockApi.drafts.create).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/drafts/draft-new?tab=funding");
  });
});
