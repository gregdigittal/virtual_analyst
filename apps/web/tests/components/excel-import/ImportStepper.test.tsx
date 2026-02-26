import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ImportStepper } from "@/components/excel-import/ImportStepper";

const ALL_LABELS = ["Upload", "Classify", "Map", "Review"];

describe("ImportStepper", () => {
  it("renders all 4 step labels", () => {
    render(<ImportStepper currentStep="upload" />);

    for (const label of ALL_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("current step has data-state='current'", () => {
    render(<ImportStepper currentStep="classify" />);

    const classifyStep = screen.getByText("Classify").closest("[data-step]")!;
    expect(classifyStep).toHaveAttribute("data-state", "current");
  });

  it("previous steps have data-state='done'", () => {
    render(<ImportStepper currentStep="map" />);

    const uploadStep = screen.getByText("Upload").closest("[data-step]")!;
    expect(uploadStep).toHaveAttribute("data-state", "done");

    const classifyStep = screen.getByText("Classify").closest("[data-step]")!;
    expect(classifyStep).toHaveAttribute("data-state", "done");
  });

  it("future steps have data-state='pending'", () => {
    render(<ImportStepper currentStep="classify" />);

    const mapStep = screen.getByText("Map").closest("[data-step]")!;
    expect(mapStep).toHaveAttribute("data-state", "pending");

    const reviewStep = screen.getByText("Review").closest("[data-step]")!;
    expect(reviewStep).toHaveAttribute("data-state", "pending");
  });
});
