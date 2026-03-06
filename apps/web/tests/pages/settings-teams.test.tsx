import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import TeamsPage from "@/app/(app)/settings/teams/page";

if (!(mockApi as Record<string, unknown>).teams) {
  (mockApi as Record<string, unknown>).teams = {
    list: vi.fn(async () => ({ teams: [], total: 0 })),
    create: vi.fn(async () => ({ team_id: "t-1" })),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <TeamsPage />
    </ToastProvider>,
  );
}

describe("TeamsSettingsPage", () => {
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
      expect(screen.getByRole("heading", { name: /Teams/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
