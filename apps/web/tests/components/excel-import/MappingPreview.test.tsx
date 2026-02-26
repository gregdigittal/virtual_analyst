import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MappingPreview, type MappingData } from "@/components/excel-import/MappingPreview";
import { ReviewPanel, type ReviewMapping } from "@/components/excel-import/ReviewPanel";

const sampleMapping: MappingData = {
  revenue: 3,
  cost: 5,
  capex: 2,
  unmapped: 1,
};

const sampleReviewMapping: ReviewMapping = {
  entityName: "Acme Corp",
  revenueStreams: ["Subscriptions", "Consulting"],
  costItems: ["Salaries", "Rent"],
  capexItems: ["Servers"],
  unmapped: ["Misc Line 42"],
};

describe("MappingPreview", () => {
  it("shows summary counts", () => {
    render(<MappingPreview mapping={sampleMapping} />);

    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("revenue")).toBeInTheDocument();
    expect(screen.getByText("cost")).toBeInTheDocument();
    expect(screen.getByText("capex")).toBeInTheDocument();
    expect(screen.getByText("unmapped")).toBeInTheDocument();
  });
});

describe("ReviewPanel", () => {
  it("renders entity name, items, and create draft button", () => {
    render(<ReviewPanel mapping={sampleReviewMapping} onCreateDraft={vi.fn()} />);

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Subscriptions")).toBeInTheDocument();
    expect(screen.getByText("Consulting")).toBeInTheDocument();
    expect(screen.getByText("Salaries")).toBeInTheDocument();
    expect(screen.getByText("Rent")).toBeInTheDocument();
    expect(screen.getByText("Servers")).toBeInTheDocument();
    expect(screen.getByText("Misc Line 42")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Draft" })).toBeInTheDocument();
  });

  it("calls onCreateDraft when button clicked", async () => {
    const user = userEvent.setup();
    const onCreateDraft = vi.fn();
    render(<ReviewPanel mapping={sampleReviewMapping} onCreateDraft={onCreateDraft} />);

    await user.click(screen.getByRole("button", { name: "Create Draft" }));

    expect(onCreateDraft).toHaveBeenCalledOnce();
  });
});
