import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import SsoPage from "@/app/(app)/settings/sso/page";

if (!(mockApi as Record<string, unknown>).sso) {
  (mockApi as Record<string, unknown>).sso = {
    getConfig: vi.fn(async () => null),
    updateConfig: vi.fn(async () => ({})),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <SsoPage />
    </ToastProvider>,
  );
}

describe("SsoPage", () => {
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
      expect(screen.getByRole("heading", { name: /SSO/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
