import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext } from "./setup";
import { ToastProvider } from "@/components/ui";
import BenchmarkPage from "@/app/(app)/benchmark/page";

function renderPage() {
  return render(
    <ToastProvider>
      <BenchmarkPage />
    </ToastProvider>,
  );
}

describe("BenchmarkPage", () => {
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
      expect(screen.getByRole("heading", { name: /Benchmarking/i })).toBeInTheDocument();
    });
  });

  it("renders heading even when auth context is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Benchmarking/i })).toBeInTheDocument();
    });
  });
});
