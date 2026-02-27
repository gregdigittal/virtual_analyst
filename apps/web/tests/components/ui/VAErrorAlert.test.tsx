import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VAErrorAlert } from "@/components/ui/VAErrorAlert";

describe("VAErrorAlert", () => {
  it("renders message with role alert", () => {
    render(<VAErrorAlert message="Something went wrong" />);
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows retry button when onRetry is provided", () => {
    render(<VAErrorAlert message="Error" onRetry={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("hides retry button when onRetry is omitted", () => {
    render(<VAErrorAlert message="Error" />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<VAErrorAlert message="Failed to load" onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("applies custom className", () => {
    render(<VAErrorAlert message="Error" className="mt-6" />);
    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("mt-6");
  });
});
