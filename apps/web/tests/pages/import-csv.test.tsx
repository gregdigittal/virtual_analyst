import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import CsvImportPage from "@/app/(app)/import/csv/page";

// Add csvImport namespace to mock API
if (!(mockApi as Record<string, unknown>).csvImport) {
  (mockApi as Record<string, unknown>).csvImport = {
    upload: vi.fn(async () => ({
      draft_session_id: "draft-1",
      scenario_id: "sc-1",
      overrides_count: 5,
    })),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <CsvImportPage />
    </ToastProvider>,
  );
}

describe("CsvImportPage", () => {
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
      expect(screen.getByRole("heading", { name: /CSV Import/i })).toBeInTheDocument();
    });
  });
});
