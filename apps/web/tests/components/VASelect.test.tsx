import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VASelect } from "../../components/ui/VASelect";

describe("VASelect", () => {
  it("renders a select element with children", () => {
    render(
      <VASelect>
        <option value="a">Option A</option>
        <option value="b">Option B</option>
      </VASelect>
    );
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("Option A")).toBeInTheDocument();
    expect(screen.getByText("Option B")).toBeInTheDocument();
  });

  it("does not render error message when no error", () => {
    render(
      <VASelect>
        <option value="a">A</option>
      </VASelect>
    );
    expect(screen.queryByText(/required/i)).not.toBeInTheDocument();
  });

  it("renders error message when error prop is provided", () => {
    render(
      <VASelect error="Please select an option">
        <option value="a">A</option>
      </VASelect>
    );
    expect(screen.getByText("Please select an option")).toBeInTheDocument();
  });

  it("sets aria-invalid when error prop is provided", () => {
    render(
      <VASelect error="Invalid selection">
        <option value="a">A</option>
      </VASelect>
    );
    const select = screen.getByRole("combobox");
    expect(select).toHaveAttribute("aria-invalid", "true");
  });

  it("does not set aria-invalid when no error", () => {
    render(
      <VASelect>
        <option value="a">A</option>
      </VASelect>
    );
    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-invalid");
  });
});
