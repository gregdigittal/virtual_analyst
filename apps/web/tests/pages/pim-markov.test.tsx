/**
 * PIM Markov and Economic Context page smoke tests.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockGetAuthContext, mockApi } from "./setup";
import MarkovPage from "@/app/(app)/pim/markov/page";
import EconomicContextPage from "@/app/(app)/pim/economic/page";

beforeEach(() => {
  mockGetAuthContext.mockResolvedValue({
    accessToken: "test-token",
    tenantId: "tenant-test",
    userId: "user-test",
    tenantIdIsFallback: false,
  });
  mockApi.pim.markov.steadyState.mockResolvedValue({ top_states: [], entropy: 0 });
  mockApi.pim.markov.topTransitions.mockResolvedValue({ transitions: [] });
});

describe("Markov State Diagram page", () => {
  it("renders page heading", async () => {
    render(<MarkovPage />);
    await waitFor(() => {
      expect(screen.getByText(/Markov State Diagram/i)).toBeTruthy();
    });
  });

  it("does not call API when auth is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    mockApi.pim.markov.steadyState.mockClear();
    render(<MarkovPage />);
    await waitFor(() => {
      expect(mockApi.pim.markov.steadyState).not.toHaveBeenCalled();
    });
  });
});

describe("Economic Context page", () => {
  beforeEach(() => {
    mockApi.pim.economic.current.mockResolvedValue({
      snapshot_id: "snap-1",
      tenant_id: "t-1",
      regime: "expansion",
      gdp_growth: 0.025,
      inflation: 0.032,
      unemployment: 0.038,
      yield_10y: 0.042,
      vix: 18.5,
      captured_at: "2026-01-01T00:00:00Z",
    });
    mockApi.pim.economic.snapshots.mockResolvedValue({ snapshots: [] });
  });

  it("renders page heading", async () => {
    render(<EconomicContextPage />);
    await waitFor(() => {
      expect(screen.getByText(/Economic Context/i)).toBeTruthy();
    });
  });

  it("shows empty state when no snapshot", async () => {
    mockApi.pim.economic.current.mockResolvedValue(null);
    render(<EconomicContextPage />);
    await waitFor(() => {
      expect(screen.getByText(/No economic snapshot available/i)).toBeTruthy();
    });
  });

  it("renders GDP growth metric when snapshot loaded", async () => {
    render(<EconomicContextPage />);
    await waitFor(() => {
      expect(screen.getByText(/GDP Growth/i)).toBeTruthy();
    });
  });

  it("does not call API when auth is null", async () => {
    mockGetAuthContext.mockResolvedValue(null);
    mockApi.pim.economic.current.mockClear();
    render(<EconomicContextPage />);
    await waitFor(() => {
      expect(mockApi.pim.economic.current).not.toHaveBeenCalled();
    });
  });
});
