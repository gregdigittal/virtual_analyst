import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { VABreadcrumb } from "@/components/ui/VABreadcrumb";

// Mock next/link to render a plain <a> tag so we can assert href values
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [k: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const items = [
  { label: "Home", href: "/" },
  { label: "Settings", href: "/settings" },
  { label: "Profile" },
];

describe("VABreadcrumb", () => {
  it("renders nav with aria-label Breadcrumb", () => {
    render(<VABreadcrumb items={items} />);
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toBeInTheDocument();
  });

  it("renders links for non-final items with href", () => {
    render(<VABreadcrumb items={items} />);
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).toHaveAttribute("href", "/");
    const settingsLink = screen.getByRole("link", { name: "Settings" });
    expect(settingsLink).toHaveAttribute("href", "/settings");
  });

  it("renders final item as span with aria-current page", () => {
    render(<VABreadcrumb items={items} />);
    const finalItem = screen.getByText("Profile");
    expect(finalItem.tagName).toBe("SPAN");
    expect(finalItem).toHaveAttribute("aria-current", "page");
  });

  it("does not render the final item as a link even if it has href", () => {
    const itemsWithFinalHref = [
      { label: "Home", href: "/" },
      { label: "Current Page", href: "/current" },
    ];
    render(<VABreadcrumb items={itemsWithFinalHref} />);
    const finalItem = screen.getByText("Current Page");
    expect(finalItem.tagName).toBe("SPAN");
    expect(finalItem).toHaveAttribute("aria-current", "page");
  });

  it("renders separators with aria-hidden", () => {
    const { container } = render(<VABreadcrumb items={items} />);
    const separators = container.querySelectorAll("[aria-hidden='true']");
    // Two separators for three items (between 1-2 and 2-3)
    expect(separators).toHaveLength(2);
    separators.forEach((sep) => {
      expect(sep.textContent).toBe("/");
    });
  });

  it("applies custom className to nav element", () => {
    render(<VABreadcrumb items={items} className="mt-4" />);
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav.className).toContain("mt-4");
  });
});
