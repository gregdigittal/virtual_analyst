import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext } from "./setup";

import { ToastProvider } from "@/components/ui";
import BudgetDetailPage from "@/app/(app)/budgets/[id]/page";

function renderPage() {
  return render(
    <ToastProvider>
      <BudgetDetailPage />
    </ToastProvider>,
  );
}

describe("BudgetDetailPage", () => {
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
      expect(screen.getByRole("heading", { name: /FY2026/i })).toBeInTheDocument();
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
