import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import OrgStructureDetailPage from "@/app/(app)/org-structures/[orgId]/page";

// The page uses useParams().orgId — the mock returns { id: "test-id-123" }
// We need to ensure orgId is available. The stableParams in setup.tsx
// only has `id`. We need to override useParams for this page.
// Actually, the mock returns a single object for ALL params keys. Let's
// add orgId to the mock params or handle it — the page accesses params.orgId.
// Since setup.tsx uses a stable object { id: "test-id-123" }, params.orgId
// will be undefined. We need to add it.

// Extend the stable params from setup to include orgId
vi.mock("next/navigation", async () => {
  const actual = await vi.importActual("next/navigation");
  const { mockReplace, mockPush, mockRefresh } = await import("./setup");
  return {
    ...actual,
    useRouter: () => ({ replace: mockReplace, push: mockPush, refresh: mockRefresh }),
    useParams: () => ({ id: "test-id-123", orgId: "org-test-123" }),
    usePathname: () => "/",
    useSearchParams: () => new URLSearchParams(),
  };
});

// Add missing orgStructures methods to mock API
if (!mockApi.orgStructures.hierarchy) {
  (mockApi.orgStructures as Record<string, unknown>).hierarchy = vi.fn(async () => ({
    roots: [],
  }));
}
if (!mockApi.orgStructures.runs) {
  (mockApi.orgStructures as Record<string, unknown>).runs = vi.fn(async () => ({
    items: [],
  }));
}
if (!mockApi.orgStructures.validate) {
  (mockApi.orgStructures as Record<string, unknown>).validate = vi.fn(async () => ({
    status: "passed",
    checks: [],
  }));
}
if (!mockApi.orgStructures.update) {
  (mockApi.orgStructures as Record<string, unknown>).update = vi.fn(async () => ({}));
}
if (!mockApi.orgStructures.run) {
  (mockApi.orgStructures as Record<string, unknown>).run = vi.fn(async () => ({}));
}
if (!mockApi.orgStructures.getRun) {
  (mockApi.orgStructures as Record<string, unknown>).getRun = vi.fn(async () => ({
    result: null,
  }));
}

// Mock the ConsolidatedResults component to avoid complex dependency issues
vi.mock("@/components/ConsolidatedResults", () => ({
  ConsolidatedResults: () => <div data-testid="consolidated-results" />,
}));

function renderPage() {
  return render(
    <ToastProvider>
      <OrgStructureDetailPage />
    </ToastProvider>,
  );
}

describe("OrgStructureDetailPage", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
    // Reset org get mock to return proper data
    (mockApi.orgStructures.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      org_id: "org-test-123",
      group_name: "Test Group",
      reporting_currency: "USD",
      status: "active",
      consolidation_method: "full",
      eliminate_intercompany: true,
      minority_interest_treatment: "proportional",
      created_at: "2026-01-01T00:00:00Z",
      entities: [],
      ownership: [],
      intercompany: [],
    });
  });

  it("renders without crashing", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Test Group/i })).toBeInTheDocument();
    });
  });
});
