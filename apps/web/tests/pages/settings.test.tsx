import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext } from "./setup";
import { ToastProvider } from "@/components/ui";
import SettingsPage from "@/app/(app)/settings/page";

function renderPage() {
  return render(
    <ToastProvider>
      <SettingsPage />
    </ToastProvider>,
  );
}

describe("SettingsPage", () => {
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
      expect(screen.getByRole("heading", { name: /Settings/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    // Settings hub has no auth gate — always renders
    expect(container).toBeTruthy();
  });
});
