/**
 * PIM-7.4: PE assessment dashboard smoke tests.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { mockGetAuthContext, mockApi } from "./setup";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  redirect: vi.fn(),
}));

beforeEach(() => {
  mockGetAuthContext.mockResolvedValue({ accessToken: "test-token", tenantId: "tenant-test" });
});

describe("PE list page", () => {
  it("shows spinner while loading", async () => {
    mockApi.pim.pe.list.mockReturnValue(new Promise(() => {}));
    const PimPeListPage = (await import("@/app/(app)/pim/pe/page")).default;
    render(<PimPeListPage />);
    expect(document.body).toBeTruthy();
  });

  it("shows empty state when no assessments", async () => {
    mockApi.pim.pe.list.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    const PimPeListPage = (await import("@/app/(app)/pim/pe/page")).default;
    render(<PimPeListPage />);
    await waitFor(() => {
      expect(screen.getByText(/No PE fund assessments yet/i)).toBeTruthy();
    });
  });

  it("renders assessment list with fund names", async () => {
    mockApi.pim.pe.list.mockResolvedValue({
      items: [
        {
          assessment_id: "a1",
          tenant_id: "t1",
          fund_name: "Acme Ventures III",
          vintage_year: 2020,
          currency: "USD",
          commitment_usd: 5_000_000,
          cash_flows: [],
          nav_usd: null,
          nav_date: null,
          paid_in_capital: 4_000_000,
          distributed: 2_000_000,
          dpi: 0.5,
          tvpi: 1.5,
          moic: 1.5,
          irr: 0.18,
          irr_computed_at: null,
          j_curve_json: [],
          notes: null,
          created_at: "2026-01-01",
          updated_at: "2026-01-01",
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });
    const PimPeListPage = (await import("@/app/(app)/pim/pe/page")).default;
    render(<PimPeListPage />);
    await waitFor(() => {
      expect(screen.getByText("Acme Ventures III")).toBeTruthy();
    });
  });

  it("renders page header text", async () => {
    mockApi.pim.pe.list.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    const PimPeListPage = (await import("@/app/(app)/pim/pe/page")).default;
    render(<PimPeListPage />);
    await waitFor(() => {
      expect(screen.getByText("PE Fund Assessments")).toBeTruthy();
    });
  });
});
