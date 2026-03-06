import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext } from "./setup";
import { ToastProvider } from "@/components/ui";
import CovenantsPage from "@/app/(app)/covenants/page";

function renderPage() {
  return render(
    <ToastProvider>
      <CovenantsPage />
    </ToastProvider>,
  );
}

describe("CovenantsPage", () => {
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
      expect(screen.getByRole("heading", { name: /Covenants/i })).toBeInTheDocument();
    });
  });

  it("renders heading even when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Covenants/i })).toBeInTheDocument();
    });
  });
});
