import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VAPagination } from "../../components/ui/VAPagination";

describe("VAPagination", () => {
  it("renders Prev and Next buttons when there are multiple pages", () => {
    render(
      <VAPagination page={2} pageSize={10} total={50} onPageChange={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: /prev/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it("returns null when total is <= pageSize (single page)", () => {
    const { container } = render(
      <VAPagination page={1} pageSize={10} total={5} onPageChange={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("disables Prev button on page 1", () => {
    render(
      <VAPagination page={1} pageSize={10} total={50} onPageChange={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
  });

  it("disables Next button on last page", () => {
    render(
      <VAPagination page={5} pageSize={10} total={50} onPageChange={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("calls onPageChange with page - 1 when Prev is clicked", async () => {
    const onPageChange = vi.fn();
    render(
      <VAPagination page={3} pageSize={10} total={50} onPageChange={onPageChange} />
    );
    await userEvent.click(screen.getByRole("button", { name: /prev/i }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("calls onPageChange with page + 1 when Next is clicked", async () => {
    const onPageChange = vi.fn();
    render(
      <VAPagination page={2} pageSize={10} total={50} onPageChange={onPageChange} />
    );
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("shows page info when total is provided", () => {
    render(
      <VAPagination page={2} pageSize={10} total={50} onPageChange={vi.fn()} />
    );
    expect(screen.getByText(/page 2 of 5/i)).toBeInTheDocument();
  });

  it("shows only page number when total is not provided but hasMore is true", () => {
    render(
      <VAPagination page={2} pageSize={10} hasMore={true} onPageChange={vi.fn()} />
    );
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });
});
