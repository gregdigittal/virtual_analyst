import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SoftGateBanner } from "@/components/SoftGateBanner";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("SoftGateBanner", () => {
  it("renders message and action link", () => {
    render(
      <SoftGateBanner message="No baseline created yet" actionLabel="Start setup" actionHref="/marketplace" />
    );
    expect(screen.getByText("No baseline created yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start setup/ })).toHaveAttribute("href", "/marketplace");
  });

  it("renders with warning styling", () => {
    const { container } = render(
      <SoftGateBanner message="Test" actionLabel="Go" actionHref="/test" />
    );
    expect(container.firstChild).toHaveClass("border-va-warning/40");
  });
});
