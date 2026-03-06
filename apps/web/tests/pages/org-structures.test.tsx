import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext } from "./setup";
import { ToastProvider } from "@/components/ui";
import OrgStructuresPage from "@/app/(app)/org-structures/page";

function renderPage() {
  return render(
    <ToastProvider>
      <OrgStructuresPage />
    </ToastProvider>,
  );
}

describe("OrgStructuresPage", () => {
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
      expect(screen.getByRole("heading", { name: /Group Structures/i })).toBeInTheDocument();
    });
  });

  it("shows empty state when no groups exist", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/No groups yet/i)).toBeInTheDocument();
    });
  });
});
