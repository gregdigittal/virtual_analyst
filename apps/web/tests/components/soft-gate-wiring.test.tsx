import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockApi, mockGetAuthContext } from "../pages/setup";

import RunsPage from "@/app/(app)/runs/page";

describe("SoftGateBanner wiring – Runs page", () => {
  beforeEach(() => {
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
  });

  it("shows banner when baselines.list returns empty", async () => {
    mockApi.baselines.list.mockResolvedValue({ items: [], limit: 50, offset: 0 } as any);
    mockApi.runs.list.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 } as any);

    render(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /No baselines found/,
      );
    });
  });

  it("hides banner when baselines exist", async () => {
    mockApi.baselines.list.mockResolvedValue({
      items: [{ baseline_id: "b-1", baseline_version: "1", status: "active", is_active: true, created_at: null }],
      limit: 50,
      offset: 0,
    } as any);
    mockApi.runs.list.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 } as any);

    render(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Runs/i })).toBeInTheDocument();
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
