import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VAInput } from "../../components/ui/VAInput";

describe("VAInput", () => {
  it("renders an input element", () => {
    render(<VAInput placeholder="Enter value" />);
    expect(screen.getByPlaceholderText("Enter value")).toBeInTheDocument();
  });

  it("does not render error message when error is not set", () => {
    render(<VAInput placeholder="test" />);
    expect(screen.queryByRole("paragraph")).not.toBeInTheDocument();
  });

  it("renders error message when error prop is provided", () => {
    render(<VAInput placeholder="test" error="This field is required" />);
    expect(screen.getByText("This field is required")).toBeInTheDocument();
  });

  it("sets aria-invalid to true when error prop is provided", () => {
    render(<VAInput placeholder="test" error="Invalid" />);
    const input = screen.getByPlaceholderText("test");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("does not set aria-invalid when no error", () => {
    render(<VAInput placeholder="test" />);
    const input = screen.getByPlaceholderText("test");
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("forwards onChange handler", async () => {
    const onChange = vi.fn();
    render(<VAInput placeholder="test" onChange={onChange} />);
    const input = screen.getByPlaceholderText("test");
    await userEvent.type(input, "x");
    expect(onChange).toHaveBeenCalled();
  });
});
