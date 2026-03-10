import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import FeedbackPage from "@/app/(app)/inbox/feedback/page";

// Add missing feedback namespace
if (!mockApi.feedback) {
  (mockApi as Record<string, unknown>).feedback = {
    list: vi.fn(async () => ({ items: [], total: 0 })),
    acknowledge: vi.fn(async () => ({ ok: true })),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <FeedbackPage />
    </ToastProvider>,
  );
}

describe("FeedbackPage", () => {
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
      expect(screen.getByRole("heading", { name: /Learning feedback/i })).toBeInTheDocument();
    });
  });

  it("does not render content when not authenticated", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("heading", { name: /Learning feedback/i })).toBeNull();
  });
});
