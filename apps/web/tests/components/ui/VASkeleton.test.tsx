import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  VASkeleton,
  VACardSkeleton,
  VAListSkeleton,
} from "@/components/ui/VASkeleton";

describe("VASkeleton", () => {
  it("renders with aria-hidden", () => {
    const { container } = render(<VASkeleton />);
    const el = container.firstElementChild!;
    expect(el).toHaveAttribute("aria-hidden", "true");
  });

  it("applies custom className", () => {
    const { container } = render(<VASkeleton className="h-4 w-full" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("h-4");
    expect(el.className).toContain("w-full");
  });
});

describe("VACardSkeleton", () => {
  it("renders with aria-hidden", () => {
    const { container } = render(<VACardSkeleton />);
    const el = container.firstElementChild!;
    expect(el).toHaveAttribute("aria-hidden", "true");
  });
});

describe("VAListSkeleton", () => {
  it("renders 4 card skeletons by default", () => {
    render(<VAListSkeleton />);
    const status = screen.getByRole("status");
    // Each VACardSkeleton is a direct child div with aria-hidden
    const cards = status.querySelectorAll(":scope > [aria-hidden='true']");
    expect(cards).toHaveLength(4);
  });

  it("renders custom count of card skeletons", () => {
    render(<VAListSkeleton count={2} />);
    const status = screen.getByRole("status");
    const cards = status.querySelectorAll(":scope > [aria-hidden='true']");
    expect(cards).toHaveLength(2);
  });

  it("has role status", () => {
    render(<VAListSkeleton />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("has aria-label Loading", () => {
    render(<VAListSkeleton />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading");
  });

  it("includes sr-only Loading text", () => {
    render(<VAListSkeleton />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.getByText("Loading...").className).toContain("sr-only");
  });
});
