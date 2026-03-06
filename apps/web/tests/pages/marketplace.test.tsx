import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext } from "./setup";
import { ToastProvider } from "@/components/ui";
import MarketplacePage from "@/app/(app)/marketplace/page";

function renderPage() {
  return render(
    <ToastProvider>
      <MarketplacePage />
    </ToastProvider>,
  );
}

describe("MarketplacePage", () => {
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
      expect(screen.getByRole("heading", { name: /Marketplace/i })).toBeInTheDocument();
    });
  });

  it("renders heading even when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Marketplace/i })).toBeInTheDocument();
    });
  });
});
