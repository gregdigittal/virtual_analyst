import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EntityHierarchyEditor, DetectedEntity } from "@/components/EntityHierarchyEditor";

const mockEntities: DetectedEntity[] = [
  { entity_name: "Parent Corp", industry: "manufacturing", is_parent: true, children: ["Sub A", "Sub B"] },
  { entity_name: "Sub A", industry: "saas", is_parent: false, children: [] },
  { entity_name: "Sub B", industry: "consulting", is_parent: false, children: [] },
];

describe("EntityHierarchyEditor", () => {
  it("renders detected entities", () => {
    render(<EntityHierarchyEditor entities={mockEntities} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("Parent Corp")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Sub A")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Sub B")).toBeInTheDocument();
  });

  it("shows industry for each entity", () => {
    render(<EntityHierarchyEditor entities={mockEntities} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("manufacturing")).toBeInTheDocument();
    expect(screen.getByDisplayValue("saas")).toBeInTheDocument();
    expect(screen.getByDisplayValue("consulting")).toBeInTheDocument();
  });

  it("has editable inputs", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<EntityHierarchyEditor entities={mockEntities} onChange={onChange} />);
    const nameInput = screen.getByDisplayValue("Parent Corp");
    await user.type(nameInput, "X");
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall[0].entity_name).toBe("Parent CorpX");
  });

  it("shows Parent badge for parent entities", () => {
    render(<EntityHierarchyEditor entities={mockEntities} onChange={vi.fn()} />);
    expect(screen.getByText("Parent")).toBeInTheDocument();
  });

  it("shows Unlinked badge for orphan entities", () => {
    const orphanEntities: DetectedEntity[] = [
      { entity_name: "Standalone LLC", industry: "retail", is_parent: false, children: [] },
    ];
    render(<EntityHierarchyEditor entities={orphanEntities} onChange={vi.fn()} />);
    expect(screen.getByText("Unlinked")).toBeInTheDocument();
  });

  it("renders empty state when no entities", () => {
    render(<EntityHierarchyEditor entities={[]} onChange={vi.fn()} />);
    expect(screen.getByText("No entities detected.")).toBeInTheDocument();
  });
});
