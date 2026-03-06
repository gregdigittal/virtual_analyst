import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import TeamDetailPage from "@/app/(app)/settings/teams/[teamId]/page";

if (!(mockApi as Record<string, unknown>).teams) {
  (mockApi as Record<string, unknown>).teams = {
    list: vi.fn(async () => ({ teams: [], total: 0 })),
    get: vi.fn(async () => ({
      team_id: "t-1",
      team_name: "Test Team",
      members: [],
    })),
    listJobFunctions: vi.fn(async () => ({ job_functions: [] })),
    create: vi.fn(async () => ({ team_id: "t-1" })),
    update: vi.fn(async () => ({ team_id: "t-1" })),
    addMember: vi.fn(async () => ({})),
    updateMember: vi.fn(async () => ({})),
    removeMember: vi.fn(async () => ({})),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <TeamDetailPage />
    </ToastProvider>,
  );
}

describe("TeamDetailPage", () => {
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
    // Page uses params.teamId which maps to stableParams (has "id" not "teamId").
    // The mock api.teams.get returns data regardless, so the page should render.
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Team details/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
