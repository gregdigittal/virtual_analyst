import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VAFormDialog } from "@/components/ui/VAFormDialog";

describe("VAFormDialog", () => {
  it("renders form fields when open", () => {
    render(
      <VAFormDialog
        open
        title="Save Template"
        fields={[
          { name: "name", label: "Template name", placeholder: "My template" },
          { name: "industry", label: "Industry tag", placeholder: "software" },
        ]}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        submitLabel="Save"
      />
    );
    expect(screen.getByText("Save Template")).toBeInTheDocument();
    expect(screen.getByLabelText("Template name")).toBeInTheDocument();
    expect(screen.getByLabelText("Industry tag")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("returns form values on submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <VAFormDialog
        open
        title="Test"
        fields={[{ name: "name", label: "Name" }]}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
        submitLabel="Save"
      />
    );
    await user.type(screen.getByLabelText("Name"), "My Template");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "My Template" });
  });

  it("calls onCancel when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <VAFormDialog
        open
        title="Test"
        fields={[{ name: "x", label: "X" }]}
        onSubmit={vi.fn()}
        onCancel={onCancel}
        submitLabel="Save"
      />
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("does not render when closed", () => {
    render(
      <VAFormDialog
        open={false}
        title="Test"
        fields={[{ name: "x", label: "X" }]}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        submitLabel="Save"
      />
    );
    expect(screen.queryByText("Test")).not.toBeInTheDocument();
  });
});
