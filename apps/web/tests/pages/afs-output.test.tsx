import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockReplace, mockGetAuthContext, mockApi } from "./setup";
import { ToastProvider } from "@/components/ui";
import AfsOutputPage from "@/app/(app)/afs/[id]/output/page";

// Add afs namespace to mock API
if (!(mockApi as Record<string, unknown>).afs) {
  (mockApi as Record<string, unknown>).afs = {
    listFrameworks: vi.fn(async () => ({ items: [{ framework_id: "fw-1", name: "IFRS", type: "standard", sections: [] }], total: 1 })),
    seedFrameworks: vi.fn(async () => ({})),
    listEngagements: vi.fn(async () => ({ items: [], total: 0 })),
    createEngagement: vi.fn(async () => ({ engagement_id: "eng-1" })),
    getEngagement: vi.fn(async () => ({
      engagement_id: "eng-1",
      entity_name: "Test Corp",
      framework_id: "fw-1",
      fiscal_year_end: "2025-12-31",
      status: "setup",
      is_consolidated: false,
    })),
    listTrialBalances: vi.fn(async () => ({ items: [], total: 0 })),
    listPriorAFS: vi.fn(async () => ({ items: [], total: 0 })),
    listDiscrepancies: vi.fn(async () => ({ items: [], total: 0 })),
    listProjections: vi.fn(async () => ({ items: [], total: 0 })),
    listSections: vi.fn(async () => ({ items: [], total: 0 })),
    listReviews: vi.fn(async () => ({ items: [], total: 0 })),
    listReviewComments: vi.fn(async () => ({ items: [], total: 0 })),
    listTaxComputations: vi.fn(async () => ({ items: [], total: 0 })),
    listOutputs: vi.fn(async () => ({ items: [], total: 0 })),
    listConsolidationEntities: vi.fn(async () => ({ items: [], total: 0 })),
    getConsolidation: vi.fn(async () => null),
    getAnalytics: vi.fn(async () => null),
    inferFramework: vi.fn(async () => ({ framework_id: "fw-2" })),
    createFramework: vi.fn(async () => ({ framework_id: "fw-2" })),
    updateEngagement: vi.fn(async () => ({})),
    uploadTrialBalance: vi.fn(async () => ({ trial_balance_id: "tb-1" })),
    uploadPriorAFS: vi.fn(async () => ({ prior_afs_id: "pa-1" })),
    reconcile: vi.fn(async () => ({})),
    setBaseSource: vi.fn(async () => ({})),
    resolveDiscrepancy: vi.fn(async () => ({})),
    createProjection: vi.fn(async () => ({ projection_id: "proj-1" })),
    rollforward: vi.fn(async () => ({})),
    draftSection: vi.fn(async () => ({ section_id: "s-1" })),
    updateSection: vi.fn(async () => ({})),
    lockSection: vi.fn(async () => ({})),
    unlockSection: vi.fn(async () => ({})),
    validateSections: vi.fn(async () => ({ valid: true, errors: [] })),
    submitReview: vi.fn(async () => ({ review_id: "r-1" })),
    approveReview: vi.fn(async () => ({})),
    rejectReview: vi.fn(async () => ({})),
    createReviewComment: vi.fn(async () => ({ comment_id: "rc-1" })),
    computeTax: vi.fn(async () => ({ computation_id: "tc-1" })),
    addTemporaryDifference: vi.fn(async () => ({})),
    generateTaxNote: vi.fn(async () => ({})),
    linkOrg: vi.fn(async () => ({})),
    runConsolidation: vi.fn(async () => ({})),
    generateOutput: vi.fn(async () => ({ output_id: "out-1" })),
    computeAnalytics: vi.fn(async () => ({ ratios: {} })),
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <AfsOutputPage />
    </ToastProvider>,
  );
}

describe("AfsOutputPage", () => {
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
      expect(mockGetAuthContext).toHaveBeenCalled();
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
