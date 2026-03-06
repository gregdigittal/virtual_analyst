import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import CompliancePage from "@/app/(app)/settings/compliance/page";

if (!(mockApi as Record<string, unknown>).compliance) {
  (mockApi as Record<string, unknown>).compliance = {
    export: vi.fn(async () => ({ data: {} })),
    anonymize: vi.fn(async () => ({})),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <CompliancePage />
    </ToastProvider>,
  );
}

describe("CompliancePage", () => {
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
      expect(screen.getByRole("heading", { name: /Compliance/i })).toBeInTheDocument();
    });
  });

  it("does not crash when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
